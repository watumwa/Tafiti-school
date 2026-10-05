from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect


class ParentPortalIsolationMiddleware:
    """Keep parent-only identities out of staff/admin endpoints."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and not user.is_superuser:
            is_staff_identity = hasattr(user, "staff_account")
            is_parent_identity = user.parent_accesses.filter(is_active=True, is_verified=True).exists()
            if is_parent_identity and not is_staff_identity and not request.path.startswith("/parent/"):
                if not settings.PARENT_PORTAL_ENABLED:
                    logout(request)
                    return redirect("login")
                return redirect("parent_dashboard")
        return self.get_response(request)
