from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from app.models import ParentAccess, ParentPortalAudit

User = get_user_model()


class ParentSetupConfirmAPIView(APIView):
    """Consume the expiring one-time parent setup link and set a private password."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        uid = str(request.data.get("uid") or "").strip()
        token = str(request.data.get("token") or "").strip()
        password = str(request.data.get("password") or "")
        confirm = str(request.data.get("confirm_password") or "")
        if not uid or not token:
            return Response({"detail": "This parent setup link is incomplete."}, status=status.HTTP_400_BAD_REQUEST)
        if password != confirm:
            return Response({"confirm_password": ["Passwords do not match."]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id, is_active=True)
        except (ValueError, TypeError, OverflowError, User.DoesNotExist):
            return Response({"detail": "This parent setup link is invalid or has expired."}, status=status.HTTP_400_BAD_REQUEST)

        accesses = ParentAccess.objects.filter(user=user, is_active=True, is_verified=True)
        setup_accesses = accesses.filter(must_change_password=True)
        if not setup_accesses.exists():
            return Response({"detail": "This setup link has already been used or parent access is no longer active."}, status=status.HTTP_400_BAD_REQUEST)
        if setup_accesses.filter(temporary_password_expires_at__isnull=True).exists() or setup_accesses.filter(
            temporary_password_expires_at__lte=timezone.now()
        ).exists():
            return Response({"detail": "This parent setup link has expired. Ask the school to issue a new one."}, status=status.HTTP_400_BAD_REQUEST)
        if not default_token_generator.check_token(user, token):
            return Response({"detail": "This parent setup link is invalid or has expired."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(password, user=user)
        except ValidationError as exc:
            return Response({"password": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save(update_fields=("password",))
        setup_accesses.update(must_change_password=False, temporary_password_expires_at=None)
        ParentPortalAudit.objects.create(
            user=user,
            action=ParentPortalAudit.ACTION_PASSWORD_CHANGED,
            details={"method": "one_time_setup_link"},
        )
        return Response({"detail": "Your parent account password has been created. You can now sign in."})
