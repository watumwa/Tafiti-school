from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from app.constants import ROLE_PRIORITY
from app.models import ParentAccess


User = get_user_model()


@dataclass(frozen=True)
class RoleContext:
    code: str
    label: str
    dashboard_path: str


ROLE_ALIASES = {
    "admin": "Admin",
    "administrator": "Admin",
    "super admin": "Admin",
    "super-admin": "Admin",
    "head teacher": "Head Teacher",
    "headteacher": "Head Teacher",
    "head master": "Head Teacher",
    "headmaster": "Head Teacher",
    "director of studies": "Director of Studies",
    "dos": "Director of Studies",
    "bursar": "Bursar",
    "finance": "Bursar",
    "class teacher": "Class Teacher",
    "teacher": "Teacher",
    "admissions officer": "Admissions Officer",
    "librarian": "Librarian",
    "library assistant": "Library Assistant",
    "support staff": "Support Staff",
    "parent": "Parent",
    "staff": "Staff",
}

CONTEXT_ROLE_PREFERENCES = {
    "admin": [
        "Admin", "Head Teacher", "Director of Studies", "Admissions Officer",
        "Librarian", "Library Assistant", "Support Staff",
    ],
    "teacher": ["Class Teacher", "Teacher"],
    "bursar": ["Bursar"],
    "parent": ["Parent"],
}


def canonical_role_label(label: str) -> str:
    normalized = " ".join(str(label or "").strip().lower().replace("/", " ").split())
    return ROLE_ALIASES.get(normalized, str(label or "Staff").strip() or "Staff")


def _role_code(label: str) -> str:
    return "_".join(canonical_role_label(label).lower().replace("/", " ").split())


def _dashboard_path(role_label: str) -> str:
    role = canonical_role_label(role_label)
    return {
        "Admin": "/dashboard/admin",
        "Head Teacher": "/dashboard/admin",
        "Director of Studies": "/dashboard/academics",
        "Bursar": "/dashboard/finance",
        "Teacher": "/dashboard/teacher",
        "Class Teacher": "/dashboard/teacher",
        "Parent": "/dashboard/parent",
        "Admissions Officer": "/dashboard/admissions",
        "Librarian": "/dashboard/library",
        "Library Assistant": "/dashboard/library",
        "Support Staff": "/dashboard/staff",
    }.get(role, "/dashboard/staff")


def find_user(identifier: str):
    """Resolve usernames, user emails, staff emails and staff contact numbers."""
    value = identifier.strip()
    if not value:
        return None

    direct = User.objects.filter(username__iexact=value).first()
    if direct:
        return direct

    return (
        User.objects.filter(
            Q(email__iexact=value)
            | Q(staff_account__staff__email__iexact=value)
            | Q(staff_account__staff__contacts__iexact=value)
        )
        .distinct()
        .first()
    )


def assigned_role_labels(user) -> list[str]:
    if user.is_superuser:
        return ["Admin"]

    roles: list[str] = []
    try:
        account = user.staff_account
        roles.extend(account.staff.roles.values_list("name", flat=True))
        if account.role_id:
            roles.append(account.role.name)
    except (AttributeError, User.staff_account.RelatedObjectDoesNotExist):
        pass

    if ParentAccess.objects.filter(user=user, is_active=True, is_verified=True).exists():
        roles.append("Parent")

    canonical = [canonical_role_label(role) for role in roles if role]
    unique_roles = list(dict.fromkeys(canonical))
    canonical_priority = [canonical_role_label(name) for name in ROLE_PRIORITY]
    priorities = {name.lower(): index for index, name in enumerate(dict.fromkeys(canonical_priority))}
    return sorted(unique_roles, key=lambda role: (priorities.get(role.lower(), len(priorities)), role))


def resolve_active_role(user, preferred_context: str | None = None, *, strict: bool = False) -> RoleContext:
    roles = assigned_role_labels(user)
    primary = roles[0] if roles else "Staff"

    context = (preferred_context or "").strip().lower()
    if context:
        exact = next(
            (
                label for label in roles
                if context in {
                    _role_code(label),
                    canonical_role_label(label).lower(),
                    canonical_role_label(label).lower().replace(" ", "_"),
                }
            ),
            None,
        )
        if exact:
            primary = exact
        else:
            candidates = CONTEXT_ROLE_PREFERENCES.get(context, [])
            compatible = next((label for label in candidates if label in roles), None)
            if compatible:
                primary = compatible
            elif strict:
                raise ValueError("The selected sign-in workspace is not assigned to this account.")

    return RoleContext(
        code=_role_code(primary),
        label=canonical_role_label(primary),
        dashboard_path=_dashboard_path(primary),
    )


def staff_must_change_password(user) -> bool:
    try:
        return bool(user.staff_account.must_change_password)
    except (AttributeError, User.staff_account.RelatedObjectDoesNotExist):
        return False


def staff_temporary_password_expired(user) -> bool:
    try:
        account = user.staff_account
    except (AttributeError, User.staff_account.RelatedObjectDoesNotExist):
        return False
    return bool(
        account.must_change_password
        and account.temporary_password_expires_at
        and account.temporary_password_expires_at <= timezone.now()
    )


def serialize_user_context(user, preferred_context: str | None = None) -> dict:
    role_labels = assigned_role_labels(user)
    role = resolve_active_role(user, preferred_context)
    parent_accesses = ParentAccess.objects.filter(user=user, is_active=True, is_verified=True)

    must_change_password = (
        staff_must_change_password(user)
        or parent_accesses.filter(must_change_password=True).exists()
    )
    dashboard_path = "/account/change-password" if must_change_password else role.dashboard_path

    return {
        "id": user.pk,
        "username": user.get_username(),
        "email": user.email,
        "name": user.get_full_name().strip() or user.get_username(),
        "role": {"code": role.code, "label": role.label},
        "roles": [{"code": _role_code(label), "label": label} for label in role_labels],
        "permissions": sorted(user.get_all_permissions()),
        "dashboard_path": dashboard_path,
        "must_change_password": must_change_password,
    }


def user_has_portal_access(user) -> bool:
    return bool(user.is_superuser or assigned_role_labels(user))


def parent_temporary_password_expired(user) -> bool:
    try:
        user.staff_account
        return False
    except (AttributeError, User.staff_account.RelatedObjectDoesNotExist):
        return ParentAccess.objects.filter(
            user=user,
            is_active=True,
            is_verified=True,
            must_change_password=True,
            temporary_password_expires_at__lte=timezone.now(),
        ).exists()


def temporary_password_expired(user) -> bool:
    return staff_temporary_password_expired(user) or parent_temporary_password_expired(user)
