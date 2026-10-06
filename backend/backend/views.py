from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db.models import Q, QuerySet, Sum
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from app.models import ParentAccess, StaffAccount

from .auth import (
    find_user,
    resolve_active_role,
    serialize_user_context,
    temporary_password_expired,
    user_has_portal_access,
)
from .models import FeeLedger, GradeMatrix, Student, User
from .serializers import (
    FeeLedgerSerializer,
    GradeMatrixSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    StudentSerializer,
    UserSerializer,
)


AuthUser = get_user_model()


class LoginRateThrottle(AnonRateThrottle):
    rate = "10/minute"


class LoginAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        identifier = serializer.validated_data["identifier"]
        password = serializer.validated_data["password"]
        candidate = find_user(identifier)

        if candidate and not candidate.is_active and candidate.check_password(password):
            return Response(
                {"code": "inactive_account", "detail": "Your account is currently inactive."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user = None
        if candidate:
            user = authenticate(request, username=candidate.get_username(), password=password)

        if not user:
            return Response(
                {"code": "invalid_credentials", "detail": "Incorrect sign-in details."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user_has_portal_access(user):
            return Response(
                {"code": "portal_access_denied", "detail": "This account has no active school portal access."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if temporary_password_expired(user):
            return Response(
                {
                    "code": "temporary_password_expired",
                    "detail": "The temporary password has expired. Contact your school administrator.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        login_context = serializer.validated_data.get("login_context")
        if login_context:
            try:
                resolve_active_role(user, login_context, strict=True)
            except ValueError:
                return Response(
                    {
                        "code": "role_context_denied",
                        "detail": "This account is not assigned to the selected workspace. Choose the role you use at this school.",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        refresh = RefreshToken.for_user(user)
        if login_context:
            refresh["portal_context"] = login_context
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": serialize_user_context(user, preferred_context=login_context),
            },
            status=status.HTTP_200_OK,
        )


class CurrentUserAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_has_portal_access(request.user):
            return Response(
                {"code": "portal_access_denied", "detail": "This account has no active school portal access."},
                status=status.HTTP_403_FORBIDDEN,
            )
        portal_context = request.auth.get("portal_context") if request.auth else None
        return Response({"user": serialize_user_context(request.user, preferred_context=portal_context)})


class PasswordResetRequestAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        users = AuthUser.objects.filter(
            Q(email__iexact=email) | Q(staff_account__staff__email__iexact=email),
            is_active=True,
        ).distinct()

        for user in users:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
            send_mail(
                subject="Reset your Tafiti password",
                message=(
                    f"Hello {user.get_full_name().strip() or user.get_username()},\n\n"
                    "Use the link below to choose a new Tafiti password:\n"
                    f"{reset_url}\n\n"
                    "If you did not request this, you can ignore this email."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )

        return Response(
            {"detail": "If an active account matches that email, password reset instructions have been sent."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user_id = force_str(urlsafe_base64_decode(serializer.validated_data["uid"]))
            user = AuthUser.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, AuthUser.DoesNotExist):
            user = None

        token = serializer.validated_data["token"]
        if not user or not default_token_generator.check_token(user, token):
            return Response(
                {"code": "invalid_reset_link", "detail": "This password reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        password = serializer.validated_data["password"]
        try:
            validate_password(password, user=user)
        except ValidationError as error:
            return Response({"password": list(error.messages)}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save(update_fields=["password"])
        ParentAccess.objects.filter(user=user).update(
            must_change_password=False,
            temporary_password_expires_at=None,
        )
        StaffAccount.objects.filter(user=user).update(
            must_change_password=False,
            temporary_password_expires_at=None,
        )
        return Response({"detail": "Your password has been reset. You can now sign in."})


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


class SecureJWTAPIView(APIView):
    """Base API view with Simple JWT enforcement and explicit Bearer header validation."""

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_bearer_token(self, request) -> str:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise AuthenticationFailed("Authorization header must be in the format: Bearer <token>")
        return auth_header.split(" ", 1)[1].strip()


class UserListAPIView(SecureJWTAPIView, generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def list(self, request, *args, **kwargs):
        self.get_bearer_token(request)
        return super().list(request, *args, **kwargs)


class StudentListAPIView(SecureJWTAPIView, generics.ListCreateAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

    def get_queryset(self) -> QuerySet[Student]:
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def list(self, request, *args, **kwargs):
        self.get_bearer_token(request)
        return super().list(request, *args, **kwargs)


class StudentDetailAPIView(SecureJWTAPIView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

    def get(self, request, *args, **kwargs):
        self.get_bearer_token(request)
        return super().get(request, *args, **kwargs)


class GradeMatrixAPIView(SecureJWTAPIView, generics.ListCreateAPIView):
    queryset = GradeMatrix.objects.select_related("student").all()
    serializer_class = GradeMatrixSerializer

    def list(self, request, *args, **kwargs):
        self.get_bearer_token(request)
        return super().list(request, *args, **kwargs)


class FeeLedgerAPIView(SecureJWTAPIView, generics.ListCreateAPIView):
    queryset = FeeLedger.objects.select_related("student").all()
    serializer_class = FeeLedgerSerializer

    def list(self, request, *args, **kwargs):
        self.get_bearer_token(request)
        return super().list(request, *args, **kwargs)


class DashboardSummaryAPIView(SecureJWTAPIView, APIView):
    """Returns a compact payload tailored for the Next.js dashboard cards."""

    def get(self, request, *args, **kwargs):
        self.get_bearer_token(request)

        students = Student.objects.count()
        fee_total = FeeLedger.objects.aggregate(total_amount=Sum("due_amount"))
        active_students = Student.objects.filter(status=Student.STATUS_ACTIVE).count()
        overdue_students = Student.objects.filter(status=Student.STATUS_OVERDUE).count()

        payload = [
            {"label": "Active Students", "value": students, "delta": "+8.4%"},
            {"label": "Fee Collection", "value": float(fee_total["total_amount"] or 0), "delta": "+12.7%"},
            {"label": "Active Enrollments", "value": active_students, "delta": "+3.1%"},
            {"label": "Overdue Accounts", "value": overdue_students, "delta": "-6.8%"},
        ]

        return Response(payload, status=status.HTTP_200_OK)
