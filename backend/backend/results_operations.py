from __future__ import annotations

from decimal import Decimal

from django.db.models import Avg, Count, Q
from rest_framework import status
from rest_framework.response import Response

from app.models import (
    AcademicClass,
    AcademicYear,
    Assessment,
    ClassRegister,
    ClassSubjectAllocation,
    ReportCycleRemark,
    Result,
    ResultBatch,
    Term,
)

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _staff_for_user, _token_context


READ_ROLES = {"Admin", "Head Teacher", "Director of Studies", "Teacher", "Class Teacher"}


def _role(request) -> str:
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_read(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in READ_ROLES)


def _current_period():
    year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.order_by("-academic_year", "-id").first()
    term = None
    if year:
        term = Term.objects.filter(academic_year=year, is_current=True).first() or Term.objects.filter(academic_year=year).order_by("term", "id").first()
    return year, term


def _assessment_queryset(request):
    year, term = _current_period()
    queryset = Assessment.objects.select_related(
        "academic_class",
        "academic_class__Class",
        "academic_class__academic_year",
        "academic_class__term",
        "assessment_type",
        "subject",
    ).order_by("academic_class__Class__name", "subject__name", "assessment_type__name")

    if year:
        queryset = queryset.filter(academic_class__academic_year=year)
    if term:
        queryset = queryset.filter(academic_class__term=term)

    role = _role(request)
    if role in {"Teacher", "Class Teacher"} and not request.user.is_superuser:
        staff = _staff_for_user(request.user)
        if not staff:
            return queryset.none()
        allowed_pairs = ClassSubjectAllocation.objects.filter(
            subject_teacher=staff,
            is_active=True,
        ).values_list("academic_class_stream__academic_class_id", "subject_id")
        allowed_pairs = list(allowed_pairs)
        if not allowed_pairs:
            return queryset.none()
        pair_query = Q()
        for class_id, subject_id in allowed_pairs:
            pair_query |= Q(academic_class_id=class_id, subject_id=subject_id)
        queryset = queryset.filter(pair_query)

    return queryset


def _status_label(batch: ResultBatch | None) -> str:
    if not batch:
        return "Not started"
    return batch.get_status_display()


def _overview(request):
    assessments = list(_assessment_queryset(request)[:2500])
    assessment_ids = [row.pk for row in assessments]
    batches = {
        row.assessment_id: row
        for row in ResultBatch.objects.filter(assessment_id__in=assessment_ids).select_related("assessment")
    }
    result_counts = {
        row["assessment_id"]: row["count"]
        for row in Result.objects.filter(assessment_id__in=assessment_ids)
        .values("assessment_id")
        .annotate(count=Count("id"))
    }
    verified_counts = {
        row["assessment_id"]: row["count"]
        for row in Result.objects.filter(assessment_id__in=assessment_ids, status="VERIFIED")
        .values("assessment_id")
        .annotate(count=Count("id"))
    }

    rows = []
    for assessment in assessments:
        batch = batches.get(assessment.pk)
        entered = result_counts.get(assessment.pk, 0)
        verified = verified_counts.get(assessment.pk, 0)
        expected = ClassRegister.objects.filter(
            academic_class_stream__academic_class=assessment.academic_class
        ).values("student_id").distinct().count()
        rows.append({
            "assessment_id": assessment.pk,
            "class": str(assessment.academic_class.Class),
            "subject": assessment.subject.name,
            "assessment": assessment.assessment_type.name,
            "date": assessment.date.isoformat(),
            "out_of": assessment.out_of,
            "entered": entered,
            "expected": expected,
            "verified": verified,
            "missing": max(expected - entered, 0),
            "status": _status_label(batch),
            "status_code": batch.status if batch else "NOT_STARTED",
        })

    batch_qs = ResultBatch.objects.filter(assessment_id__in=assessment_ids)
    return {
        "title": "Results Operations",
        "description": "A single academic results workflow from marks entry through verification, report readiness and performance review.",
        "period": {
            "academic_year": str(assessments[0].academic_class.academic_year) if assessments else "",
            "term": str(assessments[0].academic_class.term) if assessments else "",
        },
        "metrics": [
            {"label": "Assessments", "value": len(assessments), "hint": "Current academic period", "tone": "blue"},
            {"label": "Need marks", "value": sum(1 for row in rows if row["missing"] > 0), "hint": "Assessments with incomplete entry", "tone": "gold"},
            {"label": "Pending verification", "value": batch_qs.filter(status="PENDING").count(), "hint": "Submitted for checking", "tone": "violet"},
            {"label": "Verified", "value": batch_qs.filter(status="VERIFIED").count(), "hint": "Ready for reporting", "tone": "green"},
        ],
        "rows": rows,
        "role": _role(request),
    }


def _report_cards(request):
    assessments = _assessment_queryset(request)
    class_ids = list(assessments.values_list("academic_class_id", flat=True).distinct())
    classes = AcademicClass.objects.filter(pk__in=class_ids).select_related(
        "Class", "academic_year", "term"
    ).order_by("Class__name", "id")

    rows = []
    for academic_class in classes:
        student_ids = ClassRegister.objects.filter(
            academic_class_stream__academic_class=academic_class
        ).values_list("student_id", flat=True).distinct()
        students = student_ids.count()
        class_assessments = assessments.filter(academic_class=academic_class)
        total_assessments = class_assessments.count()
        verified_assessments = ResultBatch.objects.filter(
            assessment__in=class_assessments,
            status="VERIFIED",
        ).count()
        pending_assessments = ResultBatch.objects.filter(
            assessment__in=class_assessments,
            status__in=("PENDING", "FLAGGED"),
        ).count()
        remarks = ReportCycleRemark.objects.filter(
            academic_class=academic_class,
            student_id__in=student_ids,
        )
        submitted_remarks = remarks.exclude(class_teacher_submitted_at__isnull=True).count()
        approved_remarks = remarks.exclude(head_teacher_approved_at__isnull=True).count()
        ready = bool(total_assessments and verified_assessments == total_assessments and pending_assessments == 0)
        rows.append({
            "class_id": academic_class.pk,
            "class": str(academic_class.Class),
            "year": str(academic_class.academic_year),
            "term": str(academic_class.term),
            "students": students,
            "assessments": total_assessments,
            "verified_assessments": verified_assessments,
            "pending_assessments": pending_assessments,
            "submitted_remarks": submitted_remarks,
            "approved_remarks": approved_remarks,
            "status": "Ready" if ready else "In progress",
        })

    return {
        "title": "Report Cards",
        "description": "Check class readiness before previewing, printing or publishing official student reports.",
        "rows": rows,
        "metrics": [
            {"label": "Classes", "value": len(rows), "hint": "Current period", "tone": "blue"},
            {"label": "Ready", "value": sum(row["status"] == "Ready" for row in rows), "hint": "All assessment batches verified", "tone": "green"},
            {"label": "In progress", "value": sum(row["status"] != "Ready" for row in rows), "hint": "Marks or verification still pending", "tone": "gold"},
            {"label": "Students", "value": sum(row["students"] for row in rows), "hint": "Across visible classes", "tone": "violet"},
        ],
    }


def _performance(request):
    assessments = _assessment_queryset(request)
    assessment_ids = list(assessments.values_list("id", flat=True))
    verified = Result.objects.filter(
        assessment_id__in=assessment_ids,
        status="VERIFIED",
    ).select_related("assessment__subject", "assessment__academic_class__Class")

    subject_rows = [
        {
            "subject_id": row["assessment__subject_id"],
            "subject": row["assessment__subject__name"],
            "average": f"{Decimal(row['average'] or 0):.1f}",
            "results": row["results"],
        }
        for row in verified.values(
            "assessment__subject_id", "assessment__subject__name"
        ).annotate(average=Avg("score"), results=Count("id")).order_by("-average")
    ]

    class_rows = [
        {
            "class_id": row["assessment__academic_class_id"],
            "class": row["assessment__academic_class__Class__name"],
            "average": f"{Decimal(row['average'] or 0):.1f}",
            "results": row["results"],
        }
        for row in verified.values(
            "assessment__academic_class_id", "assessment__academic_class__Class__name"
        ).annotate(average=Avg("score"), results=Count("id")).order_by("-average")
    ]

    overall = verified.aggregate(value=Avg("score"))["value"] or Decimal("0")
    return {
        "title": "Performance",
        "description": "Verified-result performance only. Draft and pending marks are deliberately excluded from analytics.",
        "metrics": [
            {"label": "Verified results", "value": verified.count(), "hint": "Used in this analysis", "tone": "blue"},
            {"label": "Overall average", "value": f"{Decimal(overall):.1f}%", "hint": "Across visible verified results", "tone": "green"},
            {"label": "Subjects", "value": len(subject_rows), "hint": "With verified marks", "tone": "violet"},
            {"label": "Classes", "value": len(class_rows), "hint": "With verified marks", "tone": "gold"},
        ],
        "subjects": subject_rows,
        "classes": class_rows,
    }


class ResultsOperationsAPIView(WorkspaceBaseAPIView):
    def get(self, request, screen: str):
        if not _can_read(request):
            return Response(
                {"detail": "Your current role cannot access results operations."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if screen == "overview":
            return Response(_overview(request))
        if screen == "report-cards":
            return Response(_report_cards(request))
        if screen == "performance":
            return Response(_performance(request))
        return Response({"detail": "Unknown results operations screen."}, status=status.HTTP_404_NOT_FOUND)
