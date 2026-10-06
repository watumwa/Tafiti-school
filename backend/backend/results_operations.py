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
    AssessmentType,
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
REPORT_EDIT_ROLES = {"Admin", "Class Teacher"}
REPORT_APPROVE_ROLES = {"Admin", "Head Teacher"}


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
        if role == "Class Teacher":
            class_teacher_ids = AcademicClassStream.objects.filter(
                class_teacher=staff,
            ).values_list("academic_class_id", flat=True)
        else:
            class_teacher_ids = []
        if not allowed_pairs and not class_teacher_ids:
            return queryset.none()
        pair_query = Q(academic_class_id__in=class_teacher_ids)
        for class_id, subject_id in allowed_pairs:
            pair_query |= Q(academic_class_id=class_id, subject_id=subject_id)
        queryset = queryset.filter(pair_query)

    return queryset


def _status_label(batch: ResultBatch | None) -> str:
    if not batch:
        return "Not started"
    return batch.get_status_display()


def _report_scope(academic_class: AcademicClass):
    assessment_types = list(
        AssessmentType.objects.filter(
            assessment__academic_class=academic_class,
        ).distinct().order_by("id")
    )
    ids = [str(item.pk) for item in assessment_types]
    if not ids:
        return "period", "Current report period"
    if len(ids) == 1:
        return f"assessment:{ids[0]}", assessment_types[0].name
    return "combined:" + "-".join(ids), "Combined: " + ", ".join(item.name for item in assessment_types)


def _class_teacher_can_edit(request, academic_class: AcademicClass) -> bool:
    if request.user.is_superuser or _role(request) == "Admin":
        return True
    if _role(request) != "Class Teacher":
        return False
    staff = _staff_for_user(request.user)
    return bool(staff and AcademicClassStream.objects.filter(
        academic_class=academic_class,
        class_teacher=staff,
    ).exists())


def _can_approve_reports(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in REPORT_APPROVE_ROLES)


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
        "description": "A single academic results workflow from marks entry through verification, remarks, report approval and performance review.",
        "period": {
            "academic_year": str(assessments[0].academic_class.academic_year) if assessments else "",
            "term": str(assessments[0].academic_class.term) if assessments else "",
        },
        "metrics": [
            {"label": "Assessments", "value": len(assessments), "hint": "Current academic period", "tone": "blue"},
            {"label": "Need marks", "value": sum(1 for row in rows if row["missing"] > 0), "hint": "Assessments with incomplete entry", "tone": "gold"},
            {"label": "Pending verification", "value": batch_qs.filter(status="PENDING").count(), "hint": "Submitted for checking", "tone": "violet"},
            {"label": "Verified", "value": batch_qs.filter(status="VERIFIED").count(), "hint": "Ready for report preparation", "tone": "green"},
        ],
        "rows": rows,
        "role": _role(request),
    }


def _report_card_row(academic_class: AcademicClass, assessments):
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
        status__in=("PENDING", "FLAGGED", "DRAFT"),
    ).count()
    scope_key, scope_label = _report_scope(academic_class)
    remarks = ReportCycleRemark.objects.filter(
        academic_class=academic_class,
        scope_key=scope_key,
        student_id__in=student_ids,
    )
    submitted_remarks = remarks.exclude(class_teacher_submitted_at__isnull=True).count()
    approved_remarks = remarks.exclude(head_teacher_approved_at__isnull=True).count()
    marks_ready = bool(total_assessments and verified_assessments == total_assessments and pending_assessments == 0)
    remarks_ready = bool(students == 0 or submitted_remarks == students)
    approvals_ready = bool(students == 0 or approved_remarks == students)
    if not marks_ready:
        workflow_status = "Marks pending"
    elif not remarks_ready:
        workflow_status = "Remarks pending"
    elif not approvals_ready:
        workflow_status = "Approval pending"
    else:
        workflow_status = "Ready"
    return {
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
        "scope_key": scope_key,
        "scope_label": scope_label,
        "status": workflow_status,
    }


def _report_cards(request):
    assessments = _assessment_queryset(request)
    class_ids = list(assessments.values_list("academic_class_id", flat=True).distinct())
    classes = AcademicClass.objects.filter(pk__in=class_ids).select_related(
        "Class", "academic_year", "term"
    ).order_by("Class__name", "id")

    rows = [_report_card_row(academic_class, assessments) for academic_class in classes]
    return {
        "title": "Report Cards",
        "description": "Follow each class from verified marks through class-teacher remarks and head-teacher approval before final report output.",
        "rows": rows,
        "metrics": [
            {"label": "Classes", "value": len(rows), "hint": "Current period", "tone": "blue"},
            {"label": "Ready", "value": sum(row["status"] == "Ready" for row in rows), "hint": "Marks, remarks and approvals complete", "tone": "green"},
            {"label": "Need action", "value": sum(row["status"] != "Ready" for row in rows), "hint": "Next step shown per class", "tone": "gold"},
            {"label": "Students", "value": sum(row["students"] for row in rows), "hint": "Across visible classes", "tone": "violet"},
        ],
    }


def _remark_rows(request, academic_class: AcademicClass):
    registrations = ClassRegister.objects.filter(
        academic_class_stream__academic_class=academic_class,
    ).select_related("student").order_by("student__student_name", "student__reg_no")
    seen = set()
    students = []
    for registration in registrations:
        if registration.student_id in seen:
            continue
        seen.add(registration.student_id)
        students.append(registration.student)

    scope_key, scope_label = _report_scope(academic_class)
    remark_map = {
        row.student_id: row
        for row in ReportCycleRemark.objects.filter(
            academic_class=academic_class,
            scope_key=scope_key,
            student_id__in=[student.pk for student in students],
        )
    }
    rows = []
    for student in students:
        remark = remark_map.get(student.pk)
        if remark and remark.head_teacher_approved_at:
            state = "Approved"
        elif remark and remark.class_teacher_submitted_at:
            state = "Submitted"
        elif remark and remark.class_teacher_remark:
            state = "Draft"
        else:
            state = "Not started"
        rows.append({
            "student_id": student.pk,
            "student": student.student_name,
            "reg_no": student.reg_no or "—",
            "class_teacher_remark": remark.class_teacher_remark if remark else "",
            "head_teacher_remark": remark.head_teacher_remark if remark else "",
            "submitted_at": remark.class_teacher_submitted_at.isoformat() if remark and remark.class_teacher_submitted_at else "",
            "approved_at": remark.head_teacher_approved_at.isoformat() if remark and remark.head_teacher_approved_at else "",
            "status": state,
        })
    return scope_key, scope_label, rows


def _report_workflow(request):
    assessments = _assessment_queryset(request)
    class_ids = list(assessments.values_list("academic_class_id", flat=True).distinct())
    classes = list(AcademicClass.objects.filter(pk__in=class_ids).select_related(
        "Class", "academic_year", "term"
    ).order_by("Class__name", "id"))
    selected_id = request.query_params.get("class_id")
    selected = next((item for item in classes if str(item.pk) == str(selected_id)), None) or (classes[0] if classes else None)
    if not selected:
        return {
            "title": "Remarks & Approval",
            "description": "No report-card classes are available for the current period.",
            "classes": [],
            "selected_class_id": None,
            "rows": [],
            "permissions": {"edit": False, "approve": False},
            "metrics": [],
        }
    scope_key, scope_label, rows = _remark_rows(request, selected)
    return {
        "title": "Remarks & Approval",
        "description": "Prepare class-teacher remarks, submit them once, then complete head-teacher approval without leaving the results workspace.",
        "classes": [{"id": item.pk, "label": f"{item.Class} · {item.term}"} for item in classes],
        "selected_class_id": selected.pk,
        "selected_class": str(selected.Class),
        "scope_key": scope_key,
        "scope_label": scope_label,
        "rows": rows,
        "permissions": {
            "edit": _class_teacher_can_edit(request, selected),
            "approve": _can_approve_reports(request),
        },
        "metrics": [
            {"label": "Students", "value": len(rows), "hint": "Current class register", "tone": "blue"},
            {"label": "Draft / not started", "value": sum(row["status"] in {"Draft", "Not started"} for row in rows), "hint": "Class-teacher action needed", "tone": "gold"},
            {"label": "Submitted", "value": sum(row["status"] == "Submitted" for row in rows), "hint": "Awaiting head-teacher approval", "tone": "violet"},
            {"label": "Approved", "value": sum(row["status"] == "Approved" for row in rows), "hint": "Report remark complete", "tone": "green"},
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


def _get_report_class(request, class_id):
    if not class_id:
        return None
    allowed_ids = set(_assessment_queryset(request).values_list("academic_class_id", flat=True).distinct())
    if int(class_id) not in allowed_ids:
        return None
    return AcademicClass.objects.select_related("Class", "academic_year", "term").filter(pk=class_id).first()


@transaction.atomic
def _report_action(request):
    academic_class = _get_report_class(request, request.data.get("class_id"))
    if not academic_class:
        return Response({"detail": "Choose a valid report class."}, status=status.HTTP_400_BAD_REQUEST)
    student_id = request.data.get("student_id")
    registration = ClassRegister.objects.filter(
        academic_class_stream__academic_class=academic_class,
        student_id=student_id,
    ).select_related("student").first()
    if not registration:
        return Response({"detail": "The selected student is not registered in this class."}, status=status.HTTP_404_NOT_FOUND)
    student = registration.student
    scope_key, scope_label = _report_scope(academic_class)
    remark, _created = ReportCycleRemark.objects.select_for_update().get_or_create(
        student=student,
        academic_class=academic_class,
        scope_key=scope_key,
        defaults={"scope_label": scope_label},
    )
    action = str(request.data.get("action") or "").strip().lower()

    if action in {"save", "submit"}:
        if not _class_teacher_can_edit(request, academic_class):
            return Response({"detail": "Only the class teacher or administrator can prepare these remarks."}, status=status.HTTP_403_FORBIDDEN)
        if remark.head_teacher_approved_at:
            return Response({"detail": "This remark is already approved. Reopen the approval before editing it."}, status=status.HTTP_409_CONFLICT)
        text = " ".join(str(request.data.get("class_teacher_remark") or "").split())
        if len(text) > ReportCycleRemark.MAX_REMARK_LENGTH:
            return Response({"detail": f"Class-teacher remark cannot exceed {ReportCycleRemark.MAX_REMARK_LENGTH} characters."}, status=status.HTTP_400_BAD_REQUEST)
        if action == "submit" and not text:
            return Response({"detail": "Enter a class-teacher remark before submitting."}, status=status.HTTP_400_BAD_REQUEST)
        remark.class_teacher_remark = text
        remark.scope_label = scope_label
        remark.updated_by = request.user
        if action == "submit":
            remark.class_teacher_submitted_by = request.user
            remark.class_teacher_submitted_at = timezone.now()
            remark.head_teacher_approved_by = None
            remark.head_teacher_approved_at = None
            remark.head_teacher_remark = ""
        remark.save()
        return Response({"detail": "Remark submitted for approval." if action == "submit" else "Remark draft saved."})

    if action == "approve":
        if not _can_approve_reports(request):
            return Response({"detail": "Only the Head Teacher or administrator can approve report remarks."}, status=status.HTTP_403_FORBIDDEN)
        if not remark.class_teacher_submitted_at:
            return Response({"detail": "The class teacher must submit this remark before approval."}, status=status.HTTP_409_CONFLICT)
        head_text = " ".join(str(request.data.get("head_teacher_remark") or "").split())
        if len(head_text) > 240:
            return Response({"detail": "Head-teacher remark cannot exceed 240 characters."}, status=status.HTTP_400_BAD_REQUEST)
        remark.head_teacher_remark = head_text
        remark.head_teacher_approved_by = request.user
        remark.head_teacher_approved_at = timezone.now()
        remark.updated_by = request.user
        remark.save()
        return Response({"detail": "Report remark approved."})

    if action == "reopen":
        if not _can_approve_reports(request):
            return Response({"detail": "Only the Head Teacher or administrator can reopen an approval."}, status=status.HTTP_403_FORBIDDEN)
        remark.head_teacher_approved_by = None
        remark.head_teacher_approved_at = None
        remark.updated_by = request.user
        remark.save(update_fields=("head_teacher_approved_by", "head_teacher_approved_at", "updated_by", "updated_at"))
        return Response({"detail": "Approval reopened. The class-teacher remark can be edited again."})

    return Response({"detail": "Unknown report-card action."}, status=status.HTTP_400_BAD_REQUEST)


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
        if screen == "report-workflow":
            return Response(_report_workflow(request))
        if screen == "performance":
            return Response(_performance(request))
        return Response({"detail": "Unknown results operations screen."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, screen: str):
        if not _can_read(request):
            return Response({"detail": "Your current role cannot access results operations."}, status=status.HTTP_403_FORBIDDEN)
        if screen == "report-workflow":
            return _report_action(request)
        return Response({"detail": "Unknown results operations action."}, status=status.HTTP_404_NOT_FOUND)
