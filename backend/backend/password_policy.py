from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from app.models import ParentAccess, StaffAccount

from .auth import serialize_user_context
from .serializers import PasswordChangeSerializer


class PasswordChangeAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data["password"]
        try:
            validate_password(password, user=request.user)
        except ValidationError as error:
            return Response({"password": list(error.messages)}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(password)
        request.user.save(update_fields=["password"])
        ParentAccess.objects.filter(user=request.user).update(
            must_change_password=False,
            temporary_password_expires_at=None,
        )
        StaffAccount.objects.filter(user=request.user).update(
            must_change_password=False,
            temporary_password_expires_at=None,
        )
        return Response({"user": serialize_user_context(request.user)})
