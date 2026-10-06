from __future__ import annotations

from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.response import Response

from app.models import AdmissionApplication, AdmissionCycle, AdmissionStatusHistory, Class
from app.services.admissions import EnrollmentError, enroll_application

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context


READ_ROLES = {"Admin", "Head Teacher", "Director of Studies", "Admissions Officer"}
WRITE_ROLES = {"Admin", "Head Teacher", "Director of Studies", "Admissions Officer"}
ENROLL_ROLES = {"Admin", "Head Teacher"}

# Keep these transitions aligned with the mature Django admissions workflow.
TRANSITIONS = {
    AdmissionApplication.STATUS_DRAFT: {AdmissionApplication.STATUS_SUBMITTED, AdmissionApplication.STATUS_WITHDRAWN},
    AdmissionApplication.STATUS_SUBMITTED: {AdmissionApplication.STATUS_REVIEW, AdmissionApplication.STATUS_WITHDRAWN},
    AdmissionApplication.STATUS_REVIEW: {
        AdmissionApplication.STATUS_SHORTLISTED,
        AdmissionApplication.STATUS_WAITLISTED,
        AdmissionApplication.STATUS_REJECTED,
    },
    AdmissionApplication.STATUS_SHORTLISTED: {
        AdmissionApplication.STATUS_ASSESSMENT,
        AdmissionApplication.STATUS_INTERVIEW,
        AdmissionApplication.STATUS_ACCEPTED,
        AdmissionApplication.STATUS_WAITLISTED,
        AdmissionApplication.STATUS_REJECTED,
    },
    AdmissionApplication.STATUS_ASSESSMENT: {
        AdmissionApplication.STATUS_INTERVIEW,
        AdmissionApplication.STATUS_ACCEPTED,
        AdmissionApplication.STATUS_WAITLISTED,
        AdmissionApplication.STATUS_REJECTED,
    },
    AdmissionApplication.STATUS_INTERVIEW: {
        AdmissionApplication.STATUS_ACCEPTED,
        AdmissionApplication.STATUS_WAITLISTED,
        AdmissionApplication.STATUS_REJECTED,
    },
    AdmissionApplication.STATUS_WAITLISTED: {
        AdmissionApplication.STATUS_ACCEPTED,
        AdmissionApplication.STATUS_REJECTED,
        AdmissionApplication.STATUS_WITHDRAWN,
    },
    AdmissionApplication.STATUS_ACCEPTED: {
        AdmissionApplication.STATUS_ENROLLED,
        AdmissionApplication.STATUS_WITHDRAWN,
    },
}


def _role(request) -> str:
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_read(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in READ_ROLES)


def _can_write(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in WRITE_ROLES)


def _can_enroll(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in ENROLL_ROLES)


def _status_label(value: str) -> str:
    return dict(AdmissionApplication.STATUS_CHOICES).get(value, value.replace("_", " ").title())


def _source_label(value: str) -> str:
    return dict(AdmissionApplication.SOURCE_CHOICES).get(value, value.replace("_", " ").title())


def _date(value) -> str:
    if not value:
        return ""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _base_queryset():
    return AdmissionApplication.objects.select_related(
        "cycle",
        "cycle__academic_year",
        "applying_class",
        "preferred_stream",
        "enrolled_student",
        "created_by",
    )


def _filtered_queryset(request):
    queryset = _base_queryset().order_by("-created_at", "-id")
    query = str(request.query_params.get("q") or "").strip()
    cycle_id = str(request.query_params.get("cycle") or "").strip()
    class_id = str(request.query_params.get("class_id") or "").strip()
    date_from = parse_date(str(request.query_params.get("date_from") or ""))
    date_to = parse_date(str(request.query_params.get("date_to") or ""))

    if query:
        queryset = queryset.filter(
            Q(application_number__icontains=query)
            | Q(student_name__icontains=query)
            | Q(guardian__icontains=query)
            | Q(contact__icontains=query)
        )
    if cycle_id.isdigit():
        queryset = queryset.filter(cycle_id=int(cycle_id))
    if class_id.isdigit():
        queryset = queryset.filter(applying_class_id=int(class_id))
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return queryset


def _row(application: AdmissionApplication) -> dict:
    return {
        "id": application.pk,
        "application_number": application.application_number,
        "applicant": application.student_name,
        "gender": application.get_gender_display(),
        "class": str(application.applying_class),
        "stream": str(application.preferred_stream or "—"),
        "guardian": application.guardian,
        "contact": application.contact,
        "source": _source_label(application.source),
        "source_code": application.source,
        "status": _status_label(application.status),
        "status_code": application.status,
        "cycle": str(application.cycle),
        "created": _date(application.created_at),
        "updated": _date(application.updated_at),
        "enrolled_student_id": application.enrolled_student_id,
    }


def _list_payload(request) -> dict:
    scoped = _filtered_queryset(request)
    status_filter = str(request.query_params.get("status") or "all").strip().lower()
    known_statuses = {value for value, _ in AdmissionApplication.STATUS_CHOICES}

    counts = {value: scoped.filter(status=value).count() for value, _ in AdmissionApplication.STATUS_CHOICES}
    if status_filter in known_statuses:
        rows_queryset = scoped.filter(status=status_filter)
    else:
        status_filter = "all"
        rows_queryset = scoped

    pending_statuses = {
        AdmissionApplication.STATUS_SUBMITTED,
        AdmissionApplication.STATUS_REVIEW,
        AdmissionApplication.STATUS_SHORTLISTED,
        AdmissionApplication.STATUS_ASSESSMENT,
        AdmissionApplication.STATUS_INTERVIEW,
        AdmissionApplication.STATUS_WAITLISTED,
    }
    total = scoped.count()
    pending = sum(counts.get(value, 0) for value in pending_statuses)
    accepted = counts.get(AdmissionApplication.STATUS_ACCEPTED, 0)
    enrolled = counts.get(AdmissionApplication.STATUS_ENROLLED, 0)

    return {
        "title": "Admissions",
        "description": "Review every application from submission to a controlled student enrollment without leaving the admissions workspace.",
        "metrics": [
            {"label": "Applications", "value": total, "hint": "In the current filter scope", "tone": "blue"},
            {"label": "In progress", "value": pending, "hint": "Awaiting an admissions decision", "tone": "gold"},
            {"label": "Accepted", "value": accepted, "hint": "Ready for enrollment", "tone": "green"},
            {"label": "Enrolled", "value": enrolled, "hint": "Converted to student records", "tone": "violet"},
        ],
        "filters": {
            "status": status_filter,
            "q": str(request.query_params.get("q") or ""),
            "cycle": str(request.query_params.get("cycle") or ""),
            "class_id": str(request.query_params.get("class_id") or ""),
            "date_from": str(request.query_params.get("date_from") or ""),
            "date_to": str(request.query_params.get("date_to") or ""),
        },
        "statuses": [
            {"value": "all", "label": "All", "count": total},
            *[
                {"value": value, "label": label, "count": counts.get(value, 0)}
                for value, label in AdmissionApplication.STATUS_CHOICES
            ],
        ],
        "cycles": [
            {"id": row.pk, "label": str(row)}
            for row in AdmissionCycle.objects.select_related("academic_year").order_by("-opens_on", "-id")[:100]
        ],
        "classes": [
            {"id": row.pk, "label": str(row)}
            for row in Class.objects.order_by("name", "id")[:200]
        ],
        "rows": [_row(application) for application in rows_queryset[:2500]],
        "actions": {
            "can_create": _can_write(request),
            "can_change_status": _can_write(request),
            "can_enroll": _can_enroll(request),
        },
    }


def _detail_payload(application: AdmissionApplication, request) -> dict:
    histories = application.status_history.select_related("changed_by").order_by("changed_at", "id")
    allowed = sorted(TRANSITIONS.get(application.status, set()))
    if AdmissionApplication.STATUS_ENROLLED in allowed:
        allowed.remove(AdmissionApplication.STATUS_ENROLLED)

    today = timezone.localdate()
    cycle_open = bool(
        application.cycle.is_active
        and application.cycle.opens_on <= today <= application.cycle.closes_on
    )
    age = None
    if application.birthdate:
        age = today.year - application.birthdate.year - (
            (today.month, today.day) < (application.birthdate.month, application.birthdate.day)
        )

    enrolled_student = None
    if application.enrolled_student_id:
        enrolled_student = {
            "id": application.enrolled_student_id,
            "name": application.enrolled_student.student_name,
            "student_number": application.enrolled_student.display_student_id,
        }

    return {
        "application": {
            **_row(application),
            "birthdate": _date(application.birthdate),
            "age": age,
            "nationality": application.nationality,
            "religion": application.religion,
            "address": application.address,
            "previous_school": application.previous_school,
            "relationship": application.relationship,
            "internal_notes": application.internal_notes,
            "decision_notes": application.decision_notes,
            "cycle_open": cycle_open,
            "cycle_opens_on": _date(application.cycle.opens_on),
            "cycle_closes_on": _date(application.cycle.closes_on),
            "created_by": application.created_by.get_username() if application.created_by_id else "Public application",
        },
        "history": [
            {
                "id": row.pk,
                "from_status": _status_label(row.from_status) if row.from_status else "Started",
                "to_status": _status_label(row.to_status),
                "to_status_code": row.to_status,
                "notes": row.notes or "",
                "changed_by": row.changed_by.get_username() if row.changed_by_id else "System / public applicant",
                "changed_at": _date(row.changed_at),
            }
            for row in histories
        ],
        "allowed_transitions": [
            {"value": value, "label": _status_label(value)} for value in allowed
        ],
        "can_edit": _can_write(request) and application.status != AdmissionApplication.STATUS_ENROLLED,
        "can_change_status": _can_write(request) and bool(allowed),
        "can_enroll": (
            _can_enroll(request)
            and application.status == AdmissionApplication.STATUS_ACCEPTED
            and not application.enrolled_student_id
        ),
        "enrolled_student": enrolled_student,
    }


class AdmissionsWorkspaceAPIView(WorkspaceBaseAPIView):
    def get(self, request, screen: str, pk: int | None = None):
        if not _can_read(request):
            return Response(
                {"detail": "Your current role cannot access admissions."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if screen == "applications" and pk is None:
            return Response(_list_payload(request))

        if screen == "application" and pk is not None:
            try:
                application = _base_queryset().get(pk=pk)
            except AdmissionApplication.DoesNotExist:
                return Response(
                    {"detail": "Admission application was not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(_detail_payload(application, request))

        return Response({"detail": "Unknown admissions screen."}, status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    def post(self, request, screen: str, pk: int | None = None):
        if not _can_write(request):
            return Response(
                {"detail": "Your current role cannot change admission applications."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if screen != "application" or pk is None:
            return Response({"detail": "Unknown admissions action."}, status=status.HTTP_404_NOT_FOUND)

        try:
            application = _base_queryset().select_for_update().get(pk=pk)
        except AdmissionApplication.DoesNotExist:
            return Response(
                {"detail": "Admission application was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        action = str(request.data.get("action") or "").strip().lower()

        if action == "transition":
            target = str(request.data.get("status") or "").strip().lower()
            notes = str(request.data.get("notes") or "").strip()[:2000]
            allowed = TRANSITIONS.get(application.status, set())
            if target == AdmissionApplication.STATUS_ENROLLED or target not in allowed:
                return Response(
                    {"detail": "That admission status transition is not allowed from the current stage."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            previous = application.status
            application.status = target
            application.decision_notes = notes
            application.save(update_fields=("status", "decision_notes", "updated_at"))
            AdmissionStatusHistory.objects.create(
                application=application,
                from_status=previous,
                to_status=target,
                notes=notes,
                changed_by=request.user,
            )
            application = _base_queryset().get(pk=application.pk)
            return Response({
                "detail": f"Application moved to {_status_label(target)}.",
                "workspace": _detail_payload(application, request),
            })

        if action == "enroll":
            if not _can_enroll(request):
                return Response(
                    {"detail": "Only the Head Teacher or an administrator can complete enrollment."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if application.status != AdmissionApplication.STATUS_ACCEPTED:
                return Response(
                    {"detail": "Only an accepted application can be enrolled."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                student = enroll_application(application_id=application.pk, actor=request.user)
            except EnrollmentError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            refreshed = _base_queryset().get(pk=application.pk)
            return Response({
                "detail": f"Enrollment completed. Student number: {student.display_student_id}.",
                "student": {
                    "id": student.pk,
                    "name": student.student_name,
                    "student_number": student.display_student_id,
                },
                "workspace": _detail_payload(refreshed, request),
            }, status=status.HTTP_201_CREATED)

        return Response({"detail": "Unknown admissions action."}, status=status.HTTP_400_BAD_REQUEST)
