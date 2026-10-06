from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import get_random_string
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from app.constants import ROLE_CHOICES
from app.models import ParentAccess, Role, Staff, StaffAccount

from .auth import assigned_role_labels, canonical_role_label, resolve_active_role
from .workspace import ROLE_RESOURCES


User = get_user_model()
TEMP_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"


PERMISSION_MODULES = [
    ("students", "Students", {"students"}),
    ("staff", "Staff", {"staff"}),
    ("admissions", "Admissions", {"admissions"}),
    ("parents", "Parent access", {"parents"}),
    ("classes", "Classes", {"classes"}),
    ("subjects", "Subjects", {"subjects"}),
    ("results", "Results", {"results"}),
    ("attendance", "Attendance", {"attendance"}),
    ("timetable", "Timetable", {"timetable"}),
    ("fees", "Fees & payments", {"fees", "fees-payments", "fees-class-bills", "fees-bill-items"}),
    ("finance", "Finance", {"finance", "finance-budgets", "finance-budget-items", "finance-expenditure-items", "finance-expenses", "finance-vendors", "finance-income"}),
    ("library", "Library", {"library"}),
    ("communication", "Communication", {"communication"}),
    ("audit", "Audit", {"audit"}),
    ("settings", "Settings", {"settings"}),
]


def _token_context(request):
    auth = getattr(request, "auth", None)
    try:
        return auth.get("portal_context") if auth else None
    except AttributeError:
        return None


def _active_role(request) -> str:
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_view(request) -> bool:
    return bool(request.user.is_superuser or _active_role(request) in {"Admin", "Head Teacher"})


def _can_manage(request) -> bool:
    return bool(request.user.is_superuser or _active_role(request) == "Admin")


def _role_catalog():
    storage_by_label: dict[str, str] = {}
    for value, _label in ROLE_CHOICES:
        canonical = canonical_role_label(value)
        storage_by_label.setdefault(canonical, value)
    for role_name in Role.objects.values_list("name", flat=True):
        canonical = canonical_role_label(role_name)
        storage_by_label.setdefault(canonical, role_name)
    labels = list(storage_by_label)
    if "Parent" not in labels:
        labels.append("Parent")
    return labels, storage_by_label


def _role_matrix(labels: list[str]):
    rows = []
    for label in labels:
        allowed = ROLE_RESOURCES.get(label, set())
        rows.append({
            "label": label,
            "assignable": label != "Parent",
            "access": {
                key: bool("*" in allowed or allowed.intersection(resources))
                for key, _module_label, resources in PERMISSION_MODULES
            },
        })
    return rows


def _user_row(user):
    account = getattr(user, "staff_account", None)
    staff = account.staff if account else None
    parent_accesses = list(getattr(user, "parent_accesses", []).all()) if hasattr(user, "parent_accesses") else []
    roles = assigned_role_labels(user)
    return {
        "id": user.pk,
        "name": user.get_full_name().strip() or (str(staff) if staff else user.get_username()),
        "username": user.get_username(),
        "email": user.email or (staff.email if staff else ""),
        "photo": staff.staff_photo.url if staff and staff.staff_photo else "",
        "department": staff.department if staff else ("Parent portal" if parent_accesses else ""),
        "staff_id": staff.pk if staff else None,
        "account_type": "Staff" if staff else "Parent",
        "roles": roles,
        "active": bool(user.is_active),
        "superuser": bool(user.is_superuser),
        "last_login": user.last_login.isoformat() if user.last_login else "",
        "date_joined": user.date_joined.isoformat() if user.date_joined else "",
        "parent_links": len([row for row in parent_accesses if row.is_active and row.is_verified]),
        "can_edit_roles": bool(staff and not user.is_superuser),
        "must_change_password": bool(account and account.must_change_password),
    }


def _staff_candidate(staff):
    return {
        "id": staff.pk,
        "name": str(staff),
        "email": staff.email or "",
        "department": staff.department or "",
        "status": staff.staff_status,
        "roles": [canonical_role_label(name) for name in staff.roles.values_list("name", flat=True)],
    }


def _new_password():
    return get_random_string(14, allowed_chars=TEMP_PASSWORD_ALPHABET)


def _username_for_staff(staff):
    first_initial = (staff.first_name or "U")[0].upper()
    last_name = (staff.last_name or "staff").lower().replace(" ", "")
    base = f"{first_initial}-{last_name}"
    candidate = base
    counter = 1
    while User.objects.filter(username=candidate).exists():
        candidate = f"{base}{counter}"
        counter += 1
    return candidate


def _selected_roles(values):
    if not isinstance(values, list):
        raise ValueError("Roles must be supplied as a list.")
    selected = list(dict.fromkeys(canonical_role_label(value) for value in values if value))
    if not selected:
        raise ValueError("Choose at least one staff role.")
    if "Parent" in selected:
        raise ValueError("Parent access is managed separately from staff roles.")
    _labels, storage_by_label = _role_catalog()
    unknown = [label for label in selected if label not in storage_by_label]
    if unknown:
        raise ValueError(f"Unknown role: {unknown[0]}.")
    role_objects = []
    for label in selected:
        role, _created = Role.objects.get_or_create(name=storage_by_label[label])
        role_objects.append(role)
    return selected, role_objects


class UserRolesWorkspaceAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id: int | None = None):
        if not _can_view(request):
            return Response({"detail": "You do not have permission to view user management."}, status=status.HTTP_403_FORBIDDEN)

        users = User.objects.filter(
            Q(staff_account__isnull=False) | Q(parent_accesses__isnull=False) | Q(is_superuser=True)
        ).select_related(
            "staff_account__staff", "staff_account__role"
        ).prefetch_related(
            "staff_account__staff__roles", "parent_accesses"
        ).distinct().order_by("first_name", "last_name", "username")

        labels, _storage = _role_catalog()
        rows = [_user_row(user) for user in users]
        staff_with_accounts = {row["staff_id"] for row in rows if row["staff_id"]}
        candidates = Staff.objects.exclude(pk__in=staff_with_accounts).prefetch_related("roles").order_by("first_name", "last_name")

        return Response({
            "users": rows,
            "unprovisioned_staff": [_staff_candidate(staff) for staff in candidates[:1000]],
            "roles": _role_matrix(labels),
            "modules": [{"key": key, "label": label} for key, label, _resources in PERMISSION_MODULES],
            "summary": {
                "total_users": len(rows),
                "active_users": sum(1 for row in rows if row["active"]),
                "role_types": len(labels),
                "staff_without_accounts": candidates.count(),
            },
            "can_manage": _can_manage(request),
        })

    @transaction.atomic
    def post(self, request, user_id: int | None = None):
        if not _can_manage(request):
            return Response({"detail": "Only an administrator can create staff login accounts."}, status=status.HTTP_403_FORBIDDEN)
        if user_id:
            return Response({"detail": "Create staff accounts from the collection endpoint."}, status=status.HTTP_400_BAD_REQUEST)
        action = str(request.data.get("action") or "create_staff_account").strip().lower()
        if action != "create_staff_account":
            return Response({"detail": "Unknown user-management action."}, status=status.HTTP_400_BAD_REQUEST)
        staff = Staff.objects.select_for_update().prefetch_related("roles").filter(pk=request.data.get("staff_id")).first()
        if not staff:
            return Response({"detail": "Choose a valid staff record."}, status=status.HTTP_400_BAD_REQUEST)
        if StaffAccount.objects.filter(staff=staff).exists():
            return Response({"detail": "This staff member already has a portal account."}, status=status.HTTP_409_CONFLICT)
        requested_roles = request.data.get("roles") or [canonical_role_label(name) for name in staff.roles.values_list("name", flat=True)]
        try:
            _labels, role_objects = _selected_roles(requested_roles)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        temporary_password = _new_password()
        user = User.objects.create_user(
            username=_username_for_staff(staff),
            email=staff.email or "",
            first_name=staff.first_name,
            last_name=staff.last_name,
            password=temporary_password,
            is_active=True,
        )
        staff.roles.set(role_objects)
        account = StaffAccount.objects.create(
            staff=staff,
            user=user,
            role=role_objects[0],
            must_change_password=True,
            temporary_password_expires_at=timezone.now() + timedelta(hours=getattr(settings, "STAFF_TEMP_PASSWORD_HOURS", 24)),
        )
        return Response({
            "detail": f"Portal account created for {staff}.",
            "user": _user_row(user),
            "temporary_credential": {
                "username": user.username,
                "password": temporary_password,
                "expires_at": account.temporary_password_expires_at.isoformat(),
                "show_once": True,
            },
        }, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def patch(self, request, user_id: int | None = None):
        if not _can_manage(request):
            return Response({"detail": "Only an administrator can change user accounts and roles."}, status=status.HTTP_403_FORBIDDEN)
        if not user_id:
            return Response({"detail": "A user account is required."}, status=status.HTTP_400_BAD_REQUEST)

        target = User.objects.filter(pk=user_id).select_related(
            "staff_account__staff", "staff_account__role"
        ).prefetch_related("staff_account__staff__roles").first()
        if not target:
            return Response({"detail": "User account not found."}, status=status.HTTP_404_NOT_FOUND)

        action = str(request.data.get("action") or "").strip().lower()
        if action == "status":
            active = bool(request.data.get("active"))
            if target.pk == request.user.pk and not active:
                return Response({"detail": "You cannot deactivate the account you are currently using."}, status=status.HTTP_400_BAD_REQUEST)
            target.is_active = active
            target.save(update_fields=["is_active"])
            return Response({"detail": f"{target.get_username()} is now {'active' if active else 'inactive'}.", "user": _user_row(target)})

        if action == "reset_password":
            if target.is_superuser:
                return Response({"detail": "Use the protected password-reset flow for superuser accounts."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                account = target.staff_account
            except StaffAccount.DoesNotExist:
                return Response({"detail": "Parent passwords are reset from Parent Access."}, status=status.HTTP_400_BAD_REQUEST)
            temporary_password = _new_password()
            target.set_password(temporary_password)
            target.is_active = True
            target.save(update_fields=["password", "is_active"])
            account.must_change_password = True
            account.temporary_password_expires_at = timezone.now() + timedelta(hours=getattr(settings, "STAFF_TEMP_PASSWORD_HOURS", 24))
            account.save(update_fields=["must_change_password", "temporary_password_expires_at"])
            return Response({
                "detail": f"Temporary credential reset for {target.get_username()}.",
                "temporary_credential": {
                    "username": target.username,
                    "password": temporary_password,
                    "expires_at": account.temporary_password_expires_at.isoformat(),
                    "show_once": True,
                },
            })

        if action == "roles":
            if target.is_superuser:
                return Response({"detail": "Superuser access is managed through Django administration."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                account = target.staff_account
            except StaffAccount.DoesNotExist:
                return Response({"detail": "Role assignment is available only for staff accounts. Parent access is managed separately."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                selected, role_objects = _selected_roles(request.data.get("roles") or [])
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            if target.pk == request.user.pk and "Admin" not in selected:
                return Response({"detail": "You cannot remove your own administrator role while using this account."}, status=status.HTTP_400_BAD_REQUEST)
            account.staff.roles.set(role_objects)
            account.role = role_objects[0]
            account.save(update_fields=["role"])
            refreshed = User.objects.select_related(
                "staff_account__staff", "staff_account__role"
            ).prefetch_related("staff_account__staff__roles", "parent_accesses").get(pk=target.pk)
            return Response({"detail": f"Roles updated for {refreshed.get_full_name().strip() or refreshed.get_username()}.", "user": _user_row(refreshed)})

        return Response({"detail": "Unknown user-management action."}, status=status.HTTP_400_BAD_REQUEST)
