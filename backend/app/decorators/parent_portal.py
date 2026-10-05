from functools import wraps

from django.shortcuts import redirect

from app.models import ParentNotification
from app.services.parent_portal import active_parent_accesses


def parent_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("parent_login")
        accesses = active_parent_accesses(request.user)
        if not accesses.exists():
            return redirect("parent_login")
        if accesses.filter(must_change_password=True).exists():
            return redirect("parent_force_password")
        request.parent_accesses = accesses
        request.parent_unread_count = ParentNotification.objects.filter(
            user=request.user,
            read_at__isnull=True,
        ).count()
        return view(request, *args, **kwargs)
    return wrapped
