from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from .auth import resolve_active_role, serialize_user_context, user_has_portal_access


class RoleSwitchAPIView(APIView):
    """Issue a fresh token pair for one role already assigned to the user.

    This changes only the active portal context. It does not add roles, mutate
    permissions, or alter any school business data.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not user_has_portal_access(request.user):
            return Response(
                {"code": "portal_access_denied", "detail": "This account has no active school portal access."},
                status=status.HTTP_403_FORBIDDEN,
            )

        role_value = str(request.data.get("role") or "").strip()
        if not role_value:
            return Response(
                {"code": "role_required", "detail": "Choose a workspace to continue."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            active_role = resolve_active_role(request.user, role_value, strict=True)
        except ValueError:
            return Response(
                {"code": "role_context_denied", "detail": "That workspace is not assigned to this account."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(request.user)
        refresh["portal_context"] = active_role.code

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": serialize_user_context(request.user, preferred_context=active_role.code),
            },
            status=status.HTTP_200_OK,
        )
