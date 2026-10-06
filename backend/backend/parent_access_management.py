from __future__ import annotations

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from app.models import ParentAccess, Student
from app.services.parent_portal import (
    ParentAccessError,
    activate_parent_access,
    deactivate_parent_access,
    reset_parent_password,
)

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context


READ_ROLES = {"Admin", "Head Teacher", "Director of Studies"}
WRITE_ROLES = {"Admin"}


def _role(request) -> str:
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_read(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in READ_ROLES)


def _can_write(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in WRITE_ROLES)


def _row(access: ParentAccess) -> dict:
    return {
        "id": access.pk,
        "user_id": access.user_id,
        "parent": access.user.get_full_name().strip() or access.user.get_username(),
        "username": access.user.get_username(),
        "student_id": access.student_id,
        "student": access.student.student_name,
        "student_number": access.student.display_student_id,
        "guardian": access.student.guardian,
        "contact": access.student.contact,
        "active": bool(access.is_active),
        "verified": bool(access.is_verified),
        "must_change_password": bool(access.must_change_password),
        "password_expires_at": access.temporary_password_expires_at.isoformat() if access.temporary_password_expires_at else "",
        "permissions": {
            "academics": bool(access.can_view_academics),
            "finance": bool(access.can_view_finance),
            "attendance": bool(access.can_view_attendance),
        },
    }


def _payload(request) -> dict:
    accesses = ParentAccess.objects.select_related("user", "student").order_by("student__student_name", "id")
    linked_student_ids = set(accesses.values_list("student_id", flat=True))
    candidate_qs = Student.objects.filter(is_active=True).exclude(pk__in=linked_student_ids).order_by("student_name", "reg_no")
    students_without_access = candidate_qs.count()
    candidates = candidate_qs[:2000]
    active_count = accesses.filter(is_active=True, is_verified=True).count()
    unique_accounts = accesses.values("user_id").distinct().count()
    return {
        "title": "Parent Access",
        "description": "Activate guardian accounts, control child visibility, reset first-login credentials and deactivate access from one place.",
        "can_write": _can_write(request),
        "summary": {
            "links": accesses.count(),
            "active_links": active_count,
            "parent_accounts": unique_accounts,
            "students_without_access": students_without_access,
        },
        "rows": [_row(access) for access in accesses[:2500]],
        "candidates": [
            {
                "id": student.pk,
                "student": student.student_name,
                "student_number": student.display_student_id,
                "guardian": student.guardian,
                "contact": student.contact,
                "class": str(student.current_class or ""),
                "stream": str(student.stream or ""),
            }
            for student in candidates
            if student.contact
        ],
    }


class ParentAccessManagementAPIView(WorkspaceBaseAPIView):
    def get(self, request):
        if not _can_read(request):
            return Response({"detail": "Your current role cannot access parent account management."}, status=status.HTTP_403_FORBIDDEN)
        return Response(_payload(request))

    @transaction.atomic
    def post(self, request):
        if not _can_write(request):
            return Response({"detail": "Only an administrator can change parent access."}, status=status.HTTP_403_FORBIDDEN)

        action = str(request.data.get("action") or "").strip().lower()

        if action == "activate":
            student = Student.objects.select_for_update().filter(pk=request.data.get("student_id"), is_active=True).first()
            if not student:
                return Response({"detail": "Choose an active student."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                access = activate_parent_access(
                    student=student,
                    verified_by=request.user,
                    allow_guardian_mismatch=bool(request.data.get("allow_guardian_mismatch")),
                )
            except ParentAccessError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
            return Response({
                "detail": "Parent access activated.",
                "access": _row(access),
                "credential": {
                    "username": access.user.get_username(),
                    "temporary_password": getattr(access, "temporary_password", None),
                    "expires_at": access.temporary_password_expires_at.isoformat() if access.temporary_password_expires_at else "",
                    "display_once": True,
                },
            }, status=status.HTTP_201_CREATED)

        access = ParentAccess.objects.select_for_update().select_related("user", "student").filter(pk=request.data.get("access_id")).first()
        if not access:
            return Response({"detail": "Parent access record not found."}, status=status.HTTP_404_NOT_FOUND)

        if action == "deactivate":
            deactivate_parent_access(
                access_id=access.pk,
                actor=request.user,
                reason=str(request.data.get("reason") or "Deactivated from Tafiti parent access workspace"),
            )
            return Response({"detail": "Parent access deactivated."})

        if action == "reset_password":
            try:
                user = reset_parent_password(user_id=access.user_id, actor=request.user)
            except ParentAccessError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
            refreshed = ParentAccess.objects.get(pk=access.pk)
            return Response({
                "detail": "A new one-time parent password was generated.",
                "credential": {
                    "username": user.get_username(),
                    "temporary_password": getattr(user, "temporary_password", None),
                    "expires_at": refreshed.temporary_password_expires_at.isoformat() if refreshed.temporary_password_expires_at else "",
                    "display_once": True,
                },
            })

        if action == "permissions":
            access.can_view_academics = bool(request.data.get("academics"))
            access.can_view_finance = bool(request.data.get("finance"))
            access.can_view_attendance = bool(request.data.get("attendance"))
            access.save(update_fields=["can_view_academics", "can_view_finance", "can_view_attendance", "updated_at"])
            return Response({"detail": "Parent permissions updated.", "access": _row(access)})

        if action == "reactivate":
            try:
                reactivated = activate_parent_access(
                    student=access.student,
                    verified_by=request.user,
                    allow_guardian_mismatch=True,
                )
            except ParentAccessError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
            return Response({
                "detail": "Parent access reactivated.",
                "access": _row(reactivated),
                "credential": {
                    "username": reactivated.user.get_username(),
                    "temporary_password": getattr(reactivated, "temporary_password", None),
                    "expires_at": reactivated.temporary_password_expires_at.isoformat() if reactivated.temporary_password_expires_at else "",
                    "display_once": True,
                },
            })

        return Response({"detail": "Unknown parent access action."}, status=status.HTTP_400_BAD_REQUEST)
