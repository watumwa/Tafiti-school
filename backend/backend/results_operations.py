from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone
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


def _report_classes(request):
    year, term = _current_period()
    queryset = AcademicClass.objects.select_related("Class", "academic_year", "term").order_by("Class__name", "id")
    if year:
        queryset = queryset.filter(academic_year=year)
    if term:
        queryset = queryset.filter(term=term)

    role = _role(request)
    if role == "Class Teacher" and not request.user.is_superuser:
        staff = _staff_for_user(request.user)
        if not staff:
            return queryset.none()
        queryset = queryset.filter(class_streams__class_teacher=staff).distinct()
    elif role == "Teacher" and not request.user.is_superuser:
        staff = _staff_for_user(request.user)
        if not staff:
            return queryset.none()
        queryset = queryset.filter(
            class_streams__subjects__subject_teacher=staff,
            class_streams__subjects__is_active=True,
        ).distinct()
    return queryset


def _report_scope(academic_class: AcademicClass) -> tuple[str, str]:
    assessment_types = list(
        Assessment.objects.filter(academic_class=academic_class)
        .select_related("assessment_type")
        .order_by("assessment_type_id")
        .values_list("assessment_type_id", "assessment_type__name")
        .distinct()
    )
    if not assessment_types:
        return f"term:{academic_class.term_id}", str(academic_class.term)
    if len(assessment_types) == 1:
        assessment_type_id, name = assessment_types[0]
        return f"assessment:{assessment_type_id}", name
    ids = [str(item[0]) for item in assessment_types]
    names = [item[1] for item in assessment_types]
    return "combined:" + "-".join(ids), "Combined: " + ", ".join(names)


def _class_student_ids(academic_class: AcademicClass):
    return ClassRegister.objects.filter(
        academic_class_stream__academic_class=academic_class,
        student__is_active=True,
    ).values_list("student_id", flat=True).distinct()


def _can_edit_class_remarks(request, academic_class: AcademicClass) -> bool:
    role = _role(request)
    if request.user.is_superuser or role == "Admin":
        return True
    if role != "Class Teacher":
        return False
    staff = _staff_for_user(request.user)
    return bool(staff and academic_class.class_streams.filter(class_teacher=staff).exists())


def _can_approve_reports(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in {"Admin", "Head Teacher"})


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
    classes = list(_report_classes(request)[:500])
    rows = []
    for academic_class in classes:
        student_ids = _class_student_ids(academic_class)
        students = student_ids.count()
        class_assessments = Assessment.objects.filter(academic_class=academic_class)
        total_assessments = class_assessments.count()
        verified_assessments = ResultBatch.objects.filter(
            assessment__in=class_assessments,
            status="VERIFIED",
        ).count()
        pending_assessments = ResultBatch.objects.filter(
            assessment__in=class_assessments,
            status__in=("PENDING", "FLAGGED"),
        ).count()
        scope_key, _scope_label = _report_scope(academic_class)
        remarks = ReportCycleRemark.objects.filter(
            academic_class=academic_class,
            student_id__in=student_ids,
            scope_key=scope_key,
        )
        submitted_remarks = remarks.exclude(class_teacher_submitted_at__isnull=True).count()
        approved_remarks = remarks.exclude(head_teacher_approved_at__isnull=True).count()
        marks_ready = bool(total_assessments and verified_assessments == total_assessments and pending_assessments == 0)
        if marks_ready and students and approved_remarks == students:
            workflow_status = "Approved"
        elif marks_ready and students and submitted_remarks == students:
            workflow_status = "Awaiting approval"
        elif marks_ready:
            workflow_status = "Remarks needed"
        else:
            workflow_status = "In progress"
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
            "marks_ready": marks_ready,
            "status": "Ready" if marks_ready else "In progress",
            "workflow_status": workflow_status,
        })

    return {
        "title": "Report Cards",
        "description": "Complete report cards in one flow: verified marks, class-teacher remarks, Head Teacher approval and final reporting.",
        "rows": rows,
        "metrics": [
            {"label": "Classes", "value": len(rows), "hint": "Current period", "tone": "blue"},
            {"label": "Approved", "value": sum(row["workflow_status"] == "Approved" for row in rows), "hint": "Ready for final reporting", "tone": "green"},
            {"label": "Awaiting approval", "value": sum(row["workflow_status"] == "Awaiting approval" for row in rows), "hint": "Class remarks submitted", "tone": "violet"},
            {"label": "Need attention", "value": sum(row["workflow_status"] in {"Remarks needed", "In progress"} for row in rows), "hint": "Marks or remarks still incomplete", "tone": "gold"},
        ],
    }


def _report_card_class(request, class_id: int):
    try:
        academic_class = _report_classes(request).get(pk=class_id)
    except AcademicClass.DoesNotExist:
        return None

    student_ids = list(_class_student_ids(academic_class))
    students = {
        row.student_id: row.student
        for row in ClassRegister.objects.filter(
            academic_class_stream__academic_class=academic_class,
            student_id__in=student_ids,
        ).select_related("student").order_by("student__student_name", "student__reg_no")
    }
    scope_key, scope_label = _report_scope(academic_class)
    remarks = {
        row.student_id: row
        for row in ReportCycleRemark.objects.filter(
            academic_class=academic_class,
            student_id__in=student_ids,
            scope_key=scope_key,
        )
    }
    class_assessments = Assessment.objects.filter(academic_class=academic_class)
    assessment_count = class_assessments.count()
    verified_count = ResultBatch.objects.filter(assessment__in=class_assessments, status="VERIFIED").count()
    marks_ready = bool(assessment_count and verified_count == assessment_count)

    rows = []
    seen = set()
    for student_id in student_ids:
        if student_id in seen or student_id not in students:
            continue
        seen.add(student_id)
        student = students[student_id]
        remark = remarks.get(student_id)
        rows.append({
            "student_id": student.pk,
            "student": student.student_name,
            "reg_no": student.reg_no or "—",
            "class_teacher_remark": remark.class_teacher_remark if remark else "",
            "head_teacher_remark": remark.head_teacher_remark if remark else "",
            "submitted": bool(remark and remark.class_teacher_submitted_at),
            "approved": bool(remark and remark.head_teacher_approved_at),
            "submitted_at": remark.class_teacher_submitted_at.isoformat() if remark and remark.class_teacher_submitted_at else "",
            "approved_at": remark.head_teacher_approved_at.isoformat() if remark and remark.head_teacher_approved_at else "",
        })

    return {
        "class_id": academic_class.pk,
        "class": str(academic_class.Class),
        "year": str(academic_class.academic_year),
        "term": str(academic_class.term),
        "scope_key": scope_key,
        "scope_label": scope_label,
        "marks_ready": marks_ready,
        "assessment_count": assessment_count,
        "verified_count": verified_count,
        "students": len(rows),
        "submitted": sum(1 for row in rows if row["submitted"]),
        "approved": sum(1 for row in rows if row["approved"]),
        "can_edit_class_remarks": _can_edit_class_remarks(request, academic_class),
        "can_approve": _can_approve_reports(request),
        "rows": rows,
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


def _remarks_payload(request):
    remarks = request.data.get("remarks") or {}
    if not isinstance(remarks, dict):
        return None
    return {str(key): str(value or "").strip()[: ReportCycleRemark.MAX_REMARK_LENGTH] for key, value in remarks.items()}


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
            class_id = request.query_params.get("class_id")
            if class_id:
                try:
                    payload = _report_card_class(request, int(class_id))
                except (TypeError, ValueError):
                    payload = None
                if not payload:
                    return Response({"detail": "Report-card class not found or not available to your role."}, status=status.HTTP_404_NOT_FOUND)
                return Response(payload)
            return Response(_report_cards(request))
        if screen == "performance":
            return Response(_performance(request))
        return Response({"detail": "Unknown results operations screen."}, status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    def post(self, request, screen: str):
        if not _can_read(request):
            return Response({"detail": "Your current role cannot access results operations."}, status=status.HTTP_403_FORBIDDEN)
        if screen != "report-cards":
            return Response({"detail": "This results screen does not accept workflow actions."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

        try:
            class_id = int(request.data.get("class_id"))
            academic_class = _report_classes(request).select_for_update().get(pk=class_id)
        except (TypeError, ValueError, AcademicClass.DoesNotExist):
            return Response({"detail": "Choose a valid report-card class."}, status=status.HTTP_400_BAD_REQUEST)

        action = str(request.data.get("action") or "").strip().lower()
        student_ids = list(_class_student_ids(academic_class))
        scope_key, scope_label = _report_scope(academic_class)
        now = timezone.now()

        if action in {"save_class", "submit_class"}:
            if not _can_edit_class_remarks(request, academic_class):
                return Response({"detail": "Only the assigned Class Teacher or an administrator can prepare these remarks."}, status=status.HTTP_403_FORBIDDEN)
            remarks_payload = _remarks_payload(request)
            if remarks_payload is None:
                return Response({"detail": "Remarks must be supplied as a student-to-remark map."}, status=status.HTTP_400_BAD_REQUEST)

            missing = []
            changed = 0
            for student_id in student_ids:
                text = remarks_payload.get(str(student_id), "")
                remark, _ = ReportCycleRemark.objects.select_for_update().get_or_create(
                    student_id=student_id,
                    academic_class=academic_class,
                    scope_key=scope_key,
                    defaults={"scope_label": scope_label},
                )
                if remark.head_teacher_approved_at:
                    continue
                remark.scope_label = scope_label
                remark.class_teacher_remark = text
                remark.updated_by = request.user
                if action == "submit_class":
                    if not text:
                        missing.append(student_id)
                        continue
                    remark.class_teacher_submitted_by = request.user
                    remark.class_teacher_submitted_at = now
                else:
                    remark.class_teacher_submitted_by = None
                    remark.class_teacher_submitted_at = None
                remark.head_teacher_approved_by = None
                remark.head_teacher_approved_at = None
                remark.save()
                changed += 1

            if action == "submit_class" and missing:
                transaction.set_rollback(True)
                return Response(
                    {"detail": f"Add a class-teacher remark for all students before submitting. {len(missing)} student(s) are still missing remarks."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({"detail": "Class remarks submitted for Head Teacher approval." if action == "submit_class" else "Class remark drafts saved.", "updated": changed})

        if action == "approve_class":
            if not _can_approve_reports(request):
                return Response({"detail": "Only the Head Teacher or administrator can approve report cards."}, status=status.HTTP_403_FORBIDDEN)
            remarks = list(ReportCycleRemark.objects.select_for_update().filter(
                academic_class=academic_class,
                student_id__in=student_ids,
                scope_key=scope_key,
            ))
            submitted_ids = {row.student_id for row in remarks if row.class_teacher_submitted_at}
            missing = [student_id for student_id in student_ids if student_id not in submitted_ids]
            if missing:
                return Response({"detail": f"The class cannot be approved yet. {len(missing)} student remark(s) have not been submitted by the Class Teacher."}, status=status.HTTP_409_CONFLICT)
            approved = 0
            for remark in remarks:
                if not remark.class_teacher_submitted_at:
                    continue
                remark.head_teacher_approved_by = request.user
                remark.head_teacher_approved_at = now
                remark.updated_by = request.user
                remark.save(update_fields=["head_teacher_approved_by", "head_teacher_approved_at", "updated_by", "updated_at"])
                approved += 1
            return Response({"detail": "Report cards approved for the class and ready for final reporting.", "approved": approved})

        if action == "return_class":
            if not _can_approve_reports(request):
                return Response({"detail": "Only the Head Teacher or administrator can return report cards for revision."}, status=status.HTTP_403_FORBIDDEN)
            updated = ReportCycleRemark.objects.filter(
                academic_class=academic_class,
                student_id__in=student_ids,
                scope_key=scope_key,
            ).update(
                class_teacher_submitted_by=None,
                class_teacher_submitted_at=None,
                head_teacher_approved_by=None,
                head_teacher_approved_at=None,
                updated_by=request.user,
            )
            return Response({"detail": "Report cards returned to the Class Teacher for revision.", "updated": updated})

        return Response({"detail": "Unknown report-card action."}, status=status.HTTP_400_BAD_REQUEST)
