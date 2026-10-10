from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from app.models import AuditLog, ParentAccess, Role, RolePermission, Staff, StaffAccount

from .auth import assigned_role_labels, canonical_role_label, resolve_active_role
from .role_access import PERMISSION_MODULES, PERMISSION_MODULE_KEYS, ROLE_RESOURCES, default_module_access


User = get_user_model()
SYSTEM_ROLE_LABELS = tuple(label for label in ROLE_RESOURCES if label != "Parent")


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


def _roles_for_catalog():
    """Return one display role per canonical label, with built-ins first."""
    roles = list(Role.objects.prefetch_related("module_permissions").order_by("name"))
    selected: dict[str, Role] = {}
    for role in roles:
        label = canonical_role_label(role.name)
        existing = selected.get(label)
        if existing is None or (role.is_system and not existing.is_system):
            selected[label] = role

    order = {label: index for index, label in enumerate(SYSTEM_ROLE_LABELS)}
    return sorted(
        selected.values(),
        key=lambda role: (order.get(canonical_role_label(role.name), len(order)), canonical_role_label(role.name).lower()),
    )


def _access_for_role(role: Role) -> dict[str, bool]:
    label = canonical_role_label(role.name)
    if label == "Admin":
        return {key: True for key in PERMISSION_MODULE_KEYS}
    stored = {permission.module: permission.allowed for permission in role.module_permissions.all()}
    defaults = default_module_access(label)
    return {key: bool(stored.get(key, defaults[key])) for key in PERMISSION_MODULE_KEYS}


def _role_row(role: Role):
    label = canonical_role_label(role.name)
    is_admin = label == "Admin"
    return {
        "id": role.pk,
        "label": label,
        "description": role.description,
        "assignable": role.is_active,
        "active": role.is_active,
        "system": role.is_system,
        "can_edit_access": not is_admin,
        "can_edit_details": not role.is_system,
        "can_delete": not role.is_system,
        "access": _access_for_role(role),
    }


def _role_catalog():
    roles = _roles_for_catalog()
    storage_by_label = {
        canonical_role_label(role.name): role
        for role in roles
        if role.is_active
    }
    return roles, storage_by_label


def _replace_permissions(role: Role, access: dict[str, bool]) -> None:
    for module in PERMISSION_MODULE_KEYS:
        RolePermission.objects.update_or_create(
            role=role,
            module=module,
            defaults={"allowed": bool(access[module])},
        )


def _valid_access(payload) -> dict[str, bool] | None:
    if not isinstance(payload, dict) or set(payload) - PERMISSION_MODULE_KEYS:
        return None
    return {module: bool(payload.get(module, False)) for module in PERMISSION_MODULE_KEYS}


def _audit_role_event(request, role: Role, *, action: str, summary: str, changes: dict | None = None) -> None:
    """Create one human-readable audit item for each role-management action."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    client_ip = forwarded_for.split(",")[0].strip() or request.META.get("REMOTE_ADDR") or None
    AuditLog.objects.create(
        user=request.user,
        username=request.user.get_username(),
        ip_address=client_ip,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:4000],
        method=request.method,
        path=request.get_full_path()[:512],
        action=action,
        content_type=ContentType.objects.get_for_model(Role),
        object_id=str(role.pk),
        object_repr=summary,
        changes=changes,
        extra={"security_event": "role_management", "role": canonical_role_label(role.name)},
    )


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
    }


def _workspace_payload(request):
    users = User.objects.filter(
        Q(staff_account__isnull=False) | Q(parent_accesses__isnull=False) | Q(is_superuser=True)
    ).select_related(
        "staff_account__staff", "staff_account__role"
    ).prefetch_related(
        "staff_account__staff__roles", "parent_accesses"
    ).distinct().order_by("first_name", "last_name", "username")

    roles, _storage = _role_catalog()
    rows = [_user_row(user) for user in users]
    staff_with_accounts = {row["staff_id"] for row in rows if row["staff_id"]}
    staff_without_accounts = Staff.objects.exclude(pk__in=staff_with_accounts).count()
    role_rows = [_role_row(role) for role in roles]
    role_rows.append({
        "id": None,
        "label": "Parent",
        "description": "Managed through verified parent access links.",
        "assignable": False,
        "active": True,
        "system": True,
        "can_edit_access": False,
        "can_edit_details": False,
        "can_delete": False,
        "access": default_module_access("Parent"),
    })
    return {
        "users": rows,
        "roles": role_rows,
        "modules": [{"key": key, "label": label} for key, label, _resources in PERMISSION_MODULES],
        "summary": {
            "total_users": len(rows),
            "active_users": sum(1 for row in rows if row["active"]),
            "role_types": len(role_rows),
            "staff_without_accounts": staff_without_accounts,
        },
        "can_manage": _can_manage(request),
    }


class UserRolesWorkspaceAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id: int | None = None):
        if not _can_view(request):
            return Response({"detail": "You do not have permission to view user management."}, status=status.HTTP_403_FORBIDDEN)
        return Response(_workspace_payload(request))

    @transaction.atomic
    def patch(self, request, user_id: int | None = None):
        if not _can_manage(request):
            return Response({"detail": "Only an administrator can change user accounts and roles."}, status=status.HTTP_403_FORBIDDEN)
        if not user_id:
            return Response({"detail": "A user account is required."}, status=status.HTTP_400_BAD_REQUEST)

        target = User.objects.filter(pk=user_id).select_related(
            "staff_account__staff", "staff_account__role"
        ).prefetch_related("staff_account__staff__roles", "parent_accesses").first()
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

        if action == "roles":
            if target.is_superuser:
                return Response({"detail": "Superuser access is managed through Django administration."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                account = target.staff_account
            except StaffAccount.DoesNotExist:
                return Response({"detail": "Role assignment is available only for staff accounts. Parent access is managed separately."}, status=status.HTTP_400_BAD_REQUEST)

            selected = request.data.get("roles") or []
            if not isinstance(selected, list):
                return Response({"detail": "Roles must be supplied as a list."}, status=status.HTTP_400_BAD_REQUEST)
            selected = list(dict.fromkeys(canonical_role_label(value) for value in selected if value))
            if not selected:
                return Response({"detail": "A staff portal account must keep at least one role. Deactivate the account instead if access should stop."}, status=status.HTTP_400_BAD_REQUEST)
            if "Parent" in selected:
                return Response({"detail": "Parent access is managed from Parent Access, not staff roles."}, status=status.HTTP_400_BAD_REQUEST)
            if target.pk == request.user.pk and "Admin" not in selected:
                return Response({"detail": "You cannot remove your own administrator role while using this account."}, status=status.HTTP_400_BAD_REQUEST)

            _roles, storage_by_label = _role_catalog()
            unknown = [label for label in selected if label not in storage_by_label]
            if unknown:
                return Response({"detail": f"Unknown or inactive role: {unknown[0]}."}, status=status.HTTP_400_BAD_REQUEST)

            role_objects = [storage_by_label[label] for label in selected]
            account.staff.roles.set(role_objects)
            account.role = role_objects[0]
            account.save(update_fields=["role"])

            refreshed = User.objects.select_related(
                "staff_account__staff", "staff_account__role"
            ).prefetch_related("staff_account__staff__roles", "parent_accesses").get(pk=target.pk)
            return Response({"detail": f"Roles updated for {refreshed.get_full_name().strip() or refreshed.get_username()}.", "user": _user_row(refreshed)})

        return Response({"detail": "Unknown user-management action."}, status=status.HTTP_400_BAD_REQUEST)


class RoleManagementAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        if not _can_manage(request):
            return Response({"detail": "Only an administrator can create roles."}, status=status.HTTP_403_FORBIDDEN)
        name = " ".join(str(request.data.get("name") or "").split())
        description = str(request.data.get("description") or "").strip()[:180]
        if not name:
            return Response({"detail": "A role name is required."}, status=status.HTTP_400_BAD_REQUEST)
        if len(name) > 50:
            return Response({"detail": "Role names may be at most 50 characters."}, status=status.HTTP_400_BAD_REQUEST)
        canonical_name = canonical_role_label(name)
        if any(canonical_role_label(role.name) == canonical_name for role in Role.objects.all()):
            return Response({"detail": "A role with that name already exists."}, status=status.HTTP_400_BAD_REQUEST)

        template_id = request.data.get("template_id")
        template = Role.objects.prefetch_related("module_permissions").filter(pk=template_id, is_active=True).first() if template_id else None
        if template_id and not template:
            return Response({"detail": "Choose an active template role."}, status=status.HTTP_400_BAD_REQUEST)
        access = _access_for_role(template) if template else {key: False for key in PERMISSION_MODULE_KEYS}
        role = Role.objects.create(name=name, description=description, is_system=False)
        _replace_permissions(role, access)
        _audit_role_event(
            request,
            role,
            action=AuditLog.ACTION_CREATE,
            summary=f"Role created: {canonical_role_label(role.name)}",
            changes={"access": access, "template_id": template.pk if template else None},
        )
        role = Role.objects.prefetch_related("module_permissions").get(pk=role.pk)
        return Response({"detail": f"{name} role created.", "role": _role_row(role)}, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def patch(self, request, role_id: int):
        if not _can_manage(request):
            return Response({"detail": "Only an administrator can change roles."}, status=status.HTTP_403_FORBIDDEN)
        role = Role.objects.prefetch_related("module_permissions", "staff_members").filter(pk=role_id).first()
        if not role:
            return Response({"detail": "Role not found."}, status=status.HTTP_404_NOT_FOUND)

        action = str(request.data.get("action") or "").strip().lower()
        if action == "permissions":
            if canonical_role_label(role.name) == "Admin":
                return Response({"detail": "Admin access is protected and cannot be restricted."}, status=status.HTTP_400_BAD_REQUEST)
            access = _valid_access(request.data.get("access"))
            if access is None:
                return Response({"detail": "Provide an access value for each supported module."}, status=status.HTTP_400_BAD_REQUEST)
            _replace_permissions(role, access)
            _audit_role_event(
                request,
                role,
                action=AuditLog.ACTION_UPDATE,
                summary=f"Role permissions saved: {canonical_role_label(role.name)}",
                changes={"access": access},
            )
            role = Role.objects.prefetch_related("module_permissions").get(pk=role.pk)
            return Response({"detail": f"Permissions saved for {canonical_role_label(role.name)}.", "role": _role_row(role)})

        if action == "details":
            if role.is_system:
                return Response({"detail": "Built-in role names are protected. You can still update their module access."}, status=status.HTTP_400_BAD_REQUEST)
            name = " ".join(str(request.data.get("name") or "").split())
            description = str(request.data.get("description") or "").strip()[:180]
            if not name:
                return Response({"detail": "A role name is required."}, status=status.HTTP_400_BAD_REQUEST)
            if len(name) > 50:
                return Response({"detail": "Role names may be at most 50 characters."}, status=status.HTTP_400_BAD_REQUEST)
            duplicate = Role.objects.exclude(pk=role.pk).filter(name__iexact=name).exists()
            if duplicate or any(
                other.pk != role.pk and canonical_role_label(other.name) == canonical_role_label(name)
                for other in Role.objects.all()
            ):
                return Response({"detail": "A role with that name already exists."}, status=status.HTTP_400_BAD_REQUEST)
            role.name = name
            role.description = description
            role.save(update_fields=["name", "description"])
            _audit_role_event(
                request,
                role,
                action=AuditLog.ACTION_UPDATE,
                summary=f"Role details saved: {canonical_role_label(role.name)}",
                changes={"name": role.name, "description": role.description},
            )
            role = Role.objects.prefetch_related("module_permissions").get(pk=role.pk)
            return Response({"detail": "Role details saved.", "role": _role_row(role)})

        return Response({"detail": "Unknown role action."}, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def delete(self, request, role_id: int):
        if not _can_manage(request):
            return Response({"detail": "Only an administrator can delete roles."}, status=status.HTTP_403_FORBIDDEN)
        role = Role.objects.prefetch_related("staff_members").filter(pk=role_id).first()
        if not role:
            return Response({"detail": "Role not found."}, status=status.HTTP_404_NOT_FOUND)
        if role.is_system:
            return Response({"detail": "Built-in roles are protected from deletion."}, status=status.HTTP_400_BAD_REQUEST)
        if role.staff_members.exists():
            return Response({"detail": "Remove this role from staff accounts before deleting it."}, status=status.HTTP_400_BAD_REQUEST)
        label = canonical_role_label(role.name)
        _audit_role_event(
            request,
            role,
            action=AuditLog.ACTION_DELETE,
            summary=f"Role deleted: {label}",
            changes={"name": role.name},
        )
        role.delete()
        return Response({"detail": f"{label} role deleted."}, status=status.HTTP_200_OK)
