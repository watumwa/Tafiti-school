from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from app.models import (
    AcademicClass,
    AcademicClassStream,
    AcademicYear,
    Assessment,
    ClassRegister,
    ClassSubjectAllocation,
    ReportCycleRemark,
    Result,
    ResultBatch,
    Student,
    Term,
)

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _staff_for_user, _token_context


READ_ROLES = {"Admin", "Head Teacher", "Director of Studies", "Teacher", "Class Teacher"}
REPORT_APPROVAL_ROLES = {"Admin", "Head Teacher"}


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

    # A class teacher must be able to prepare the whole class report even when
    # they only teach some of its subjects.
    if _role(request) == "Class Teacher" and not request.user.is_superuser:
        staff = _staff_for_user(request.user)
        if staff:
            class_ids.extend(
                AcademicClassStream.objects.filter(class_teacher=staff).values_list("academic_class_id", flat=True)
            )
    class_ids = list(dict.fromkeys(class_ids))

    classes = AcademicClass.objects.filter(pk__in=class_ids).select_related(
        "Class", "academic_year", "term"
    ).order_by("Class__name", "id")

    rows = []
    for academic_class in classes:
        student_ids = ClassRegister.objects.filter(
            academic_class_stream__academic_class=academic_class,
            student__is_active=True,
        ).values_list("student_id", flat=True).distinct()
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
        assessment_ids = list(class_assessments.order_by("id").values_list("id", flat=True))
        scope_key = _report_scope_key(academic_class, assessment_ids)
        remarks = ReportCycleRemark.objects.filter(
            academic_class=academic_class,
            scope_key=scope_key,
            student_id__in=student_ids,
        )
        submitted_remarks = remarks.exclude(class_teacher_submitted_at__isnull=True).count()
        approved_remarks = remarks.exclude(head_teacher_approved_at__isnull=True).count()
        ready = bool(total_assessments and verified_assessments == total_assessments and pending_assessments == 0)
        report_ready = bool(ready and students and approved_remarks == students)
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
            "status": "Approved" if report_ready else ("Ready for remarks" if ready else "In progress"),
            "can_prepare": _can_prepare_report_class(request, academic_class),
            "can_approve": _can_approve_report(request),
        })

    return {
        "title": "Report Cards",
        "description": "Prepare class-teacher remarks, complete head-teacher approval and finish report cards without leaving the results workflow.",
        "rows": rows,
        "metrics": [
            {"label": "Classes", "value": len(rows), "hint": "Current period", "tone": "blue"},
            {"label": "Ready for remarks", "value": sum(row["status"] == "Ready for remarks" for row in rows), "hint": "All assessment batches verified", "tone": "green"},
            {"label": "Approved", "value": sum(row["status"] == "Approved" for row in rows), "hint": "All learner reports approved", "tone": "violet"},
            {"label": "Students", "value": sum(row["students"] for row in rows), "hint": "Across visible classes", "tone": "gold"},
        ],
    }


def _report_scope_key(academic_class: AcademicClass, assessment_ids: list[int]) -> str:
    suffix = ",".join(str(value) for value in assessment_ids) or "none"
    return f"class:{academic_class.pk}:assessments:{suffix}"


def _report_scope_label(academic_class: AcademicClass) -> str:
    return f"{academic_class.academic_year} · {academic_class.term} · {academic_class.Class}"


def _can_prepare_report_class(request, academic_class: AcademicClass) -> bool:
    if request.user.is_superuser or _role(request) == "Admin":
        return True
    if _role(request) != "Class Teacher":
        return False
    staff = _staff_for_user(request.user)
    return bool(staff and AcademicClassStream.objects.filter(
        academic_class=academic_class,
        class_teacher=staff,
    ).exists())


def _can_approve_report(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in REPORT_APPROVAL_ROLES)


def _can_view_report_class(request, academic_class: AcademicClass) -> bool:
    if request.user.is_superuser or _role(request) in {"Admin", "Head Teacher", "Director of Studies"}:
        return True
    if _can_prepare_report_class(request, academic_class):
        return True
    staff = _staff_for_user(request.user)
    return bool(staff and ClassSubjectAllocation.objects.filter(
        subject_teacher=staff,
        academic_class_stream__academic_class=academic_class,
        is_active=True,
    ).exists())


def _report_class_payload(request, academic_class: AcademicClass) -> dict:
    assessments = list(Assessment.objects.filter(academic_class=academic_class).order_by("id"))
    assessment_ids = [row.pk for row in assessments]
    scope_key = _report_scope_key(academic_class, assessment_ids)
    scope_label = _report_scope_label(academic_class)
    student_ids = list(ClassRegister.objects.filter(
        academic_class_stream__academic_class=academic_class,
        student__is_active=True,
    ).values_list("student_id", flat=True).distinct())
    students = list(Student.objects.filter(pk__in=student_ids).order_by("student_name", "reg_no"))
    remarks = {
        row.student_id: row
        for row in ReportCycleRemark.objects.filter(
            academic_class=academic_class,
            scope_key=scope_key,
            student_id__in=student_ids,
        ).select_related("class_teacher_submitted_by", "head_teacher_approved_by")
    }
    verified_batches = ResultBatch.objects.filter(
        assessment_id__in=assessment_ids,
        status="VERIFIED",
    ).count()
    pending_batches = ResultBatch.objects.filter(
        assessment_id__in=assessment_ids,
        status__in=("PENDING", "FLAGGED"),
    ).count()
    ready = bool(assessment_ids and verified_batches == len(assessment_ids) and pending_batches == 0)

    rows = []
    for student in students:
        remark = remarks.get(student.pk)
        rows.append({
            "student_id": student.pk,
            "student_number": student.display_student_id,
            "student": student.student_name,
            "photo": student.photo.url if getattr(student, "photo", None) else "",
            "class_teacher_remark": remark.class_teacher_remark if remark else "",
            "submitted": bool(remark and remark.class_teacher_submitted_at),
            "submitted_at": remark.class_teacher_submitted_at.isoformat() if remark and remark.class_teacher_submitted_at else "",
            "head_teacher_remark": remark.head_teacher_remark if remark else "",
            "approved": bool(remark and remark.head_teacher_approved_at),
            "approved_at": remark.head_teacher_approved_at.isoformat() if remark and remark.head_teacher_approved_at else "",
        })

    return {
        "title": f"{academic_class.Class} Report Cards",
        "description": "Review verified results, prepare learner remarks and complete approval from one class workspace.",
        "class_id": academic_class.pk,
        "class": str(academic_class.Class),
        "year": str(academic_class.academic_year),
        "term": str(academic_class.term),
        "scope_key": scope_key,
        "scope_label": scope_label,
        "ready": ready,
        "assessments": len(assessment_ids),
        "verified_assessments": verified_batches,
        "pending_assessments": pending_batches,
        "students": len(students),
        "submitted": sum(1 for row in rows if row["submitted"]),
        "approved": sum(1 for row in rows if row["approved"]),
        "rows": rows,
        "permissions": {
            "prepare": _can_prepare_report_class(request, academic_class),
            "approve": _can_approve_report(request),
        },
    }


def _save_report_remarks(request, academic_class: AcademicClass, *, submit: bool = False) -> int:
    if not _can_prepare_report_class(request, academic_class):
        raise PermissionError("Your current role cannot prepare class-teacher remarks for this class.")
    assessments = list(Assessment.objects.filter(academic_class=academic_class).order_by("id"))
    assessment_ids = [row.pk for row in assessments]
    if submit:
        verified = ResultBatch.objects.filter(assessment_id__in=assessment_ids, status="VERIFIED").count()
        pending = ResultBatch.objects.filter(assessment_id__in=assessment_ids, status__in=("PENDING", "FLAGGED")).count()
        if not assessment_ids or verified != len(assessment_ids) or pending:
            raise ValueError("All assessment batches must be verified before class-teacher remarks can be submitted.")
    scope_key = _report_scope_key(academic_class, assessment_ids)
    scope_label = _report_scope_label(academic_class)
    allowed_student_ids = set(ClassRegister.objects.filter(
        academic_class_stream__academic_class=academic_class,
        student__is_active=True,
    ).values_list("student_id", flat=True))
    remarks_payload = request.data.get("remarks") or {}
    if not isinstance(remarks_payload, dict):
        raise ValueError("Remarks must be supplied as a student-to-remark mapping.")

    changed = 0
    now = timezone.now()
    for raw_student_id, raw_text in remarks_payload.items():
        try:
            student_id = int(raw_student_id)
        except (TypeError, ValueError):
            continue
        if student_id not in allowed_student_ids:
            continue
        text = str(raw_text or "").strip()
        if len(text) > ReportCycleRemark.MAX_REMARK_LENGTH:
            raise ValueError(f"A class-teacher remark cannot exceed {ReportCycleRemark.MAX_REMARK_LENGTH} characters.")
        remark, _ = ReportCycleRemark.objects.get_or_create(
            student_id=student_id,
            academic_class=academic_class,
            scope_key=scope_key,
            defaults={"scope_label": scope_label},
        )
        if remark.class_teacher_remark != text:
            remark.class_teacher_remark = text
            # Changing a previously approved learner report makes it require approval again.
            remark.head_teacher_approved_at = None
            remark.head_teacher_approved_by = None
        remark.scope_label = scope_label
        remark.updated_by = request.user
        update_fields = ["class_teacher_remark", "scope_label", "updated_by", "updated_at", "head_teacher_approved_at", "head_teacher_approved_by"]
        if submit and text:
            remark.class_teacher_submitted_at = now
            remark.class_teacher_submitted_by = request.user
            update_fields.extend(["class_teacher_submitted_at", "class_teacher_submitted_by"])
        remark.save(update_fields=update_fields)
        changed += 1
    return changed


def _approve_report_remarks(request, academic_class: AcademicClass) -> int:
    if not _can_approve_report(request):
        raise PermissionError("Only an administrator or Head Teacher can approve report cards.")
    assessments = list(Assessment.objects.filter(academic_class=academic_class).order_by("id"))
    assessment_ids = [row.pk for row in assessments]
    verified = ResultBatch.objects.filter(assessment_id__in=assessment_ids, status="VERIFIED").count()
    pending = ResultBatch.objects.filter(assessment_id__in=assessment_ids, status__in=("PENDING", "FLAGGED")).count()
    if not assessment_ids or verified != len(assessment_ids) or pending:
        raise ValueError("All assessment batches must be verified before report cards can be approved.")
    scope_key = _report_scope_key(academic_class, assessment_ids)
    head_payload = request.data.get("head_remarks") or {}
    if not isinstance(head_payload, dict):
        raise ValueError("Head-teacher remarks must be supplied as a student-to-remark mapping.")

    submitted = ReportCycleRemark.objects.filter(
        academic_class=academic_class,
        scope_key=scope_key,
        class_teacher_submitted_at__isnull=False,
    )
    now = timezone.now()
    approved = 0
    for remark in submitted:
        text = str(head_payload.get(str(remark.student_id), head_payload.get(remark.student_id, remark.head_teacher_remark)) or "").strip()
        if len(text) > 240:
            raise ValueError("A head-teacher remark cannot exceed 240 characters.")
        remark.head_teacher_remark = text
        remark.head_teacher_approved_at = now
        remark.head_teacher_approved_by = request.user
        remark.updated_by = request.user
        remark.save(update_fields=[
            "head_teacher_remark", "head_teacher_approved_at", "head_teacher_approved_by", "updated_by", "updated_at"
        ])
        approved += 1
    return approved


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
    def get(self, request, screen: str, pk: int | None = None):
        if not _can_read(request):
            return Response(
                {"detail": "Your current role cannot access results operations."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if screen == "overview" and pk is None:
            return Response(_overview(request))
        if screen == "report-cards" and pk is None:
            return Response(_report_cards(request))
        if screen == "report-class" and pk is not None:
            academic_class = AcademicClass.objects.select_related("Class", "academic_year", "term").filter(pk=pk).first()
            if not academic_class:
                return Response({"detail": "Academic class not found."}, status=status.HTTP_404_NOT_FOUND)
            if not _can_view_report_class(request, academic_class):
                return Response({"detail": "Your current role cannot view report cards for this class."}, status=status.HTTP_403_FORBIDDEN)
            return Response(_report_class_payload(request, academic_class))
        if screen == "performance" and pk is None:
            return Response(_performance(request))
        return Response({"detail": "Unknown results operations screen."}, status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    def post(self, request, screen: str, pk: int | None = None):
        if not _can_read(request):
            return Response({"detail": "Your current role cannot access results operations."}, status=status.HTTP_403_FORBIDDEN)
        if screen != "report-class" or pk is None:
            return Response({"detail": "Unknown results operation."}, status=status.HTTP_404_NOT_FOUND)
        academic_class = AcademicClass.objects.select_for_update().select_related("Class", "academic_year", "term").filter(pk=pk).first()
        if not academic_class:
            return Response({"detail": "Academic class not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_view_report_class(request, academic_class):
            return Response({"detail": "Your current role cannot manage report cards for this class."}, status=status.HTTP_403_FORBIDDEN)

        action = str(request.data.get("action") or "").strip().lower()
        try:
            if action == "save_remarks":
                changed = _save_report_remarks(request, academic_class, submit=False)
                detail = f"Saved {changed} class-teacher remark draft(s)."
            elif action == "submit_remarks":
                changed = _save_report_remarks(request, academic_class, submit=True)
                detail = f"Submitted {changed} completed class-teacher remark(s) for approval."
            elif action == "approve_remarks":
                changed = _approve_report_remarks(request, academic_class)
                detail = f"Approved {changed} learner report(s)."
            else:
                return Response({"detail": "Unknown report-card action."}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": detail, "report": _report_class_payload(request, academic_class)})
