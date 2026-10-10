"""Runtime compatibility patches for legacy Django-template routes.

The Next.js workspace is the primary UI, but legacy routes remain reachable during
migration. These wrappers ensure those routes use the same one-time parent setup
link security model instead of exposing a shared temporary credential.
"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from app.decorators.decorators import role_required_any
from app.decorators.features import feature_required
from app.models import Student
from app.services.parent_portal import ParentAccessError, activate_parent_access, reset_parent_password
from app.views import parent_portal as legacy


PARENT_MANAGEMENT_ROLES = ("Admin", "Head Teacher", "Head master", "Director of Studies")


@feature_required("PARENT_PORTAL_ENABLED")
@role_required_any(*PARENT_MANAGEMENT_ROLES)
def secure_parent_access_activate(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    if request.method == "POST":
        try:
            access = activate_parent_access(
                student=student,
                verified_by=request.user,
                allow_guardian_mismatch=request.POST.get("confirm_shared_contact") == "yes",
            )
            if access.must_change_password:
                messages.success(
                    request,
                    f"Parent access activated for {access.user.username}. Share this one-time setup link securely: {access.setup_url}",
                )
            else:
                messages.success(
                    request,
                    f"Linked to the existing parent account {access.user.username}; its private password was not changed.",
                )
        except ParentAccessError as exc:
            messages.error(request, str(exc))
    return redirect("student_details_page", id=student.pk)


@feature_required("PARENT_PORTAL_ENABLED")
@role_required_any(*PARENT_MANAGEMENT_ROLES)
def secure_parent_password_reset(request, user_id):
    if request.method == "POST":
        try:
            user = reset_parent_password(user_id=user_id, actor=request.user)
            messages.success(
                request,
                f"Parent password setup was reset for {user.username}. Share this one-time setup link securely: {user.setup_url}",
            )
        except ParentAccessError as exc:
            messages.error(request, str(exc))
    return redirect("parent_access_management")


# Patch the module attributes before app.urls imports `*` from parent_portal.
legacy.parent_access_activate = secure_parent_access_activate
legacy.parent_password_reset = secure_parent_password_reset
