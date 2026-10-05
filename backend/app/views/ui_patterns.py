from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from app.decorators.decorators import role_required_any


@login_required
@role_required_any("Admin", "Super Admin", "Super-Admin")
def ui_patterns_view(request):
    """Internal reference for approved staff-interface components and states."""
    return render(request, "ux/ui_patterns.html")

