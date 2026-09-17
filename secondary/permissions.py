from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from app.models.classes import AcademicClassStream
from app.services.teacher_assignments import get_teacher_assignments


SECONDARY_MANAGER_ROLES = {
    "Admin",
    "Head Teacher",
    "Head master",
    "Director of Studies",
    "DOS",
}
SECONDARY_ACADEMIC_ROLES = SECONDARY_MANAGER_ROLES | {
    "Teacher",
    "Class Teacher",
}


def get_effective_secondary_role(request):
    if getattr(request.user, "is_superuser", False):
        return "Admin"

    active_role = request.session.get("active_role_name")
    if active_role:
        return active_role

    staff_account = getattr(request.user, "staff_account", None)
    if staff_account and getattr(staff_account, "role", None):
        return staff_account.role.name

    if staff_account and getattr(staff_account, "staff", None):
        return staff_account.staff.roles.values_list("name", flat=True).first()

    return None


def get_secondary_staff(request):
    staff_account = getattr(request.user, "staff_account", None)
    return getattr(staff_account, "staff", None)


def has_secondary_role(request, allowed_roles):
    role = get_effective_secondary_role(request)
    if getattr(request.user, "is_superuser", False):
        return True
    return role in set(allowed_roles)


def secondary_role_required(allowed_roles, error_message, *, redirect_name="secondary:dashboard"):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if has_secondary_role(request, allowed_roles):
                return view_func(request, *args, **kwargs)
            messages.error(request, error_message)
            return redirect(redirect_name)

        return _wrapped

    return decorator


def user_can_access_secondary_academic_class(request, academic_class, subject=None):
    role = get_effective_secondary_role(request)
    if getattr(request.user, "is_superuser", False) or role in SECONDARY_MANAGER_ROLES:
        return True

    staff = get_secondary_staff(request)
    if not staff or academic_class is None:
        return False

    if role == "Class Teacher":
        return AcademicClassStream.objects.filter(
            academic_class=academic_class,
            class_teacher=staff,
        ).exists()

    if role == "Teacher":
        subject_id = getattr(subject, "id", subject)
        assignments = get_teacher_assignments(staff, academic_classes=[academic_class])
        if subject_id is None:
            return bool(assignments)
        return any(assignment.subject_id == subject_id for assignment in assignments)

    return False
