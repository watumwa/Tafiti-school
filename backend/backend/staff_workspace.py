from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from app.constants import DOCUMENT_TYPES
from app.models import (
    AttendanceSession,
    AuditLog,
    ClassSubjectAllocation,
    Staff,
    StaffAccount,
    StaffDocument,
)

from .auth import canonical_role_label, resolve_active_role


def _token_context(request) -> str | None:
    auth = getattr(request, "auth", None)
    if auth is None:
        return None
    try:
        return auth.get("portal_context")
    except Exception:
        return None


def _active_role(request) -> str:
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_view_staff(request) -> bool:
    return bool(
        request.user.is_superuser
        or _active_role(request) in {"Admin", "Head Teacher", "Director of Studies"}
    )


def _base_path(request) -> str:
    return resolve_active_role(request.user, _token_context(request)).dashboard_path


def _entity_path(request, resource: str, pk: int, *, tab: str | None = None) -> str:
    path = f"{_base_path(request)}/{resource}/{pk}"
    return f"{path}?tab={tab}" if tab else path


def _safe_file_url(value) -> str:
    if not value:
        return ""
    try:
        return value.url
    except Exception:
        return ""


def _date(value) -> str:
    if not value:
        return ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _tab(key, label, columns, rows, description, empty_title):
    return {
        "key": key,
        "label": label,
        "count": len(rows),
        "description": description,
        "columns": [{"key": column[0], "label": column[1]} for column in columns],
        "rows": rows,
        "empty_title": empty_title,
    }


def _detail_rows(items):
    return [{"field": label, "value": str(value) if value not in (None, "") else "—"} for label, value in items]


def _audit_rows(staff, limit=30):
    try:
        content_type = ContentType.objects.get_for_model(staff, for_concrete_model=False)
        return [
            {
                "when": _date(row.timestamp),
                "action": row.get_action_display(),
                "by": row.username or str(row.user or "System"),
                "summary": row.object_repr or str(staff),
            }
            for row in AuditLog.objects.filter(
                content_type=content_type,
                object_id=str(staff.pk),
            ).select_related("user").order_by("-timestamp")[:limit]
        ]
    except Exception:
        # Audit history must never make the staff profile unavailable.
        return []


class StaffWorkspaceAPIView(APIView):
    """Compatibility-safe staff profile endpoint.

    The production database can temporarily lag the newest StaffDocument model
    during rolling deployments. Reading full StaffDocument instances would make
    Django SELECT every model column (including newly added fields), turning a
    harmless schema lag into a 500 for the entire staff profile. This endpoint
    selects only the long-standing columns needed by the UI.
    """

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        if not _can_view_staff(request):
            return Response(
                {"detail": "Your current workspace cannot view staff profiles."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            staff = Staff.objects.prefetch_related("roles").get(pk=pk)
        except Staff.DoesNotExist:
            return Response({"detail": "Staff member not found."}, status=status.HTTP_404_NOT_FOUND)

        allocations = list(
            ClassSubjectAllocation.objects.filter(subject_teacher=staff)
            .select_related(
                "subject",
                "academic_class_stream",
                "academic_class_stream__academic_class__Class",
                "academic_class_stream__stream",
            )
            .order_by("subject__name")[:100]
        )
        sessions = list(
            AttendanceSession.objects.filter(teacher=staff)
            .select_related("subject", "class_stream")
            .order_by("-date")[:100]
        )

        # IMPORTANT: values() intentionally avoids selecting newer optional
        # StaffDocument fields such as uploaded_at on older production schemas.
        try:
            document_rows = list(
                StaffDocument.objects.filter(staff_id=staff.pk)
                .values("id", "document_type", "file")
                .order_by("-id")[:50]
            )
        except Exception:
            # Documents are secondary information. A document-table problem
            # should not prevent administrators from opening a staff profile.
            document_rows = []

        account = (
            StaffAccount.objects.filter(staff=staff)
            .select_related("user", "role")
            .first()
        )
        roles = list(staff.roles.values_list("name", flat=True))
        document_labels = dict(DOCUMENT_TYPES)

        tabs = [
            _tab(
                "overview",
                "Overview",
                [("field", "Profile"), ("value", "Details")],
                _detail_rows([
                    ("Full name", staff),
                    ("Gender", staff.get_gender_display()),
                    ("Date of birth", _date(staff.birth_date)),
                    ("Contact", staff.contacts),
                    ("Email", staff.email),
                    ("Address", staff.address),
                ]),
                "Staff identity and contact information.",
                "No profile details are available.",
            ),
            _tab(
                "employment",
                "Employment",
                [("field", "Employment"), ("value", "Details")],
                _detail_rows([
                    ("Department", staff.get_department_display()),
                    ("Hire date", _date(staff.hire_date)),
                    ("Qualification", staff.qualification),
                    ("Roles", ", ".join(roles) or "—"),
                    ("Academic staff", "Yes" if staff.is_academic_staff else "No"),
                    ("Administrator", "Yes" if staff.is_administrator_staff else "No"),
                ]),
                "Employment status and school responsibilities.",
                "No employment details are available.",
            ),
            _tab(
                "teaching",
                "Teaching",
                [("class", "Class"), ("stream", "Stream"), ("subject", "Subject"), ("status", "Status")],
                [
                    {
                        "class": str(row.academic_class_stream.academic_class.Class),
                        "stream": str(row.academic_class_stream.stream),
                        "subject": row.subject.name,
                        "status": "Active" if row.is_active else "Inactive",
                    }
                    for row in allocations
                ],
                "Classes and subjects assigned to this staff member.",
                "No teaching allocations have been assigned.",
            ),
            _tab(
                "attendance",
                "Attendance",
                [("date", "Date"), ("class", "Class"), ("subject", "Subject"), ("status", "Status")],
                [
                    {
                        "date": _date(row.date),
                        "class": str(row.class_stream),
                        "subject": row.subject.name,
                        "status": "Locked" if row.is_locked else "Open",
                    }
                    for row in sessions
                ],
                "Recent attendance sessions taught by this staff member.",
                "No attendance sessions were found.",
            ),
            _tab(
                "documents",
                "Documents",
                [("type", "Document"), ("file", "File")],
                [
                    {
                        "type": document_labels.get(row["document_type"], row["document_type"]),
                        "file": str(row["file"]).rsplit("/", 1)[-1] if row["file"] else "—",
                    }
                    for row in document_rows
                ],
                "Employment documents attached to this profile.",
                "No staff documents have been uploaded.",
            ),
            _tab(
                "account",
                "Account & role",
                [("field", "Account"), ("value", "Details")],
                _detail_rows([
                    ("Username", account.user.get_username() if account else "Not provisioned"),
                    ("Account email", account.user.email if account else "—"),
                    ("Primary role", account.role if account else "—"),
                    ("Account active", "Yes" if account and account.user.is_active else "No"),
                ]),
                "Login identity and primary role.",
                "No account has been provisioned.",
            ),
            _tab(
                "activity",
                "Activity",
                [("when", "When"), ("action", "Action"), ("by", "By"), ("summary", "Summary")],
                _audit_rows(staff),
                "Auditable changes to this staff record.",
                "No audit history was found.",
            ),
        ]

        actions = [
            {"label": "Teaching", "href": _entity_path(request, "staff", staff.pk, tab="teaching"), "icon": "subject"},
            {"label": "Attendance", "href": _entity_path(request, "staff", staff.pk, tab="attendance"), "icon": "attendance"},
            {"label": "Account & role", "href": _entity_path(request, "staff", staff.pk, tab="account"), "icon": "user"},
        ]
        if request.user.is_superuser or _active_role(request) in {"Admin", "Head Teacher"}:
            actions.insert(0, {"label": "Edit staff", "action": "edit", "icon": "edit", "primary": True})

        return Response(
            {
                "resource": "staff",
                "id": staff.pk,
                "eyebrow": "Staff workspace",
                "title": str(staff),
                "subtitle": f"Staff #{staff.pk}",
                "photo": _safe_file_url(staff.staff_photo),
                "status": staff.staff_status,
                "metadata": [
                    {"label": "Department", "value": staff.get_department_display()},
                    {"label": "Roles", "value": ", ".join(roles) or "—"},
                    {"label": "Email", "value": staff.email},
                    {"label": "Contact", "value": staff.contacts},
                ],
                "metrics": [
                    {"label": "Teaching allocations", "value": len(allocations), "hint": "Active and historical", "tone": "blue"},
                    {"label": "Attendance sessions", "value": len(sessions), "hint": "Most recent 100", "tone": "green"},
                    {"label": "Documents", "value": len(document_rows), "hint": "Employment files", "tone": "violet"},
                    {"label": "Account", "value": "Active" if account and account.user.is_active else "Not active", "hint": "School login", "tone": "gold"},
                ],
                "tabs": tabs,
                "actions": actions,
            },
            status=status.HTTP_200_OK,
        )
