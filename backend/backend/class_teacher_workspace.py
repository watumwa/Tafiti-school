from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from app.models import (
    AcademicClassStream,
    AcademicYear,
    Assessment,
    AttendanceRecord,
    ClassRegister,
    ReportCycleRemark,
    Result,
    Term,
    Timetable,
)
from app.models.attendance import AttendanceStatus
from app.models.timetables import WeekDay

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _safe_file_url, _staff_for_user, _token_context


WEEKDAY_CODES = {
    0: WeekDay.MONDAY,
    1: WeekDay.TUESDAY,
    2: WeekDay.WEDNESDAY,
    3: WeekDay.THURSDAY,
    4: WeekDay.FRIDAY,
    5: WeekDay.SATURDAY,
    6: WeekDay.SUNDAY,
}


def _role(request) -> str:
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _current_period():
    year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.order_by("-academic_year", "-id").first()
    term = None
    if year:
        term = Term.objects.filter(academic_year=year, is_current=True).first()
        if not term:
            term = Term.objects.filter(academic_year=year).order_by("term", "id").first()
    return year, term


def _report_scope_key(academic_class_id: int) -> str:
    assessment_types = list(
        Assessment.objects.filter(academic_class_id=academic_class_id)
        .order_by("assessment_type_id")
        .values_list("assessment_type_id", flat=True)
        .distinct()
    )
    if not assessment_types:
        academic_class = AcademicClassStream.objects.filter(academic_class_id=academic_class_id).select_related("academic_class__term").first()
        return f"term:{academic_class.academic_class.term_id}" if academic_class else "term:unknown"
    if len(assessment_types) == 1:
        return f"assessment:{assessment_types[0]}"
    return "combined:" + "-".join(str(item) for item in assessment_types)


def _percentage(score, out_of) -> Decimal | None:
    if not out_of:
        return None
    try:
        return (Decimal(score) * Decimal("100")) / Decimal(out_of)
    except (ArithmeticError, TypeError, ValueError):
        return None


def _status_label(today_records: list[str]) -> str:
    if not today_records:
        return "Not marked"
    if AttendanceStatus.ABSENT in today_records:
        return "Absent"
    if AttendanceStatus.LATE in today_records:
        return "Late"
    if AttendanceStatus.EXCUSED in today_records:
        return "Excused"
    if AttendanceStatus.PRESENT in today_records:
        return "Present"
    return "Not marked"


class ClassTeacherWorkspaceAPIView(WorkspaceBaseAPIView):
    """A read model for the Class Teacher's daily class-management workspace."""

    def get(self, request):
        role = _role(request)
        if not request.user.is_superuser and role != "Class Teacher":
            return Response(
                {"detail": "The My Class workspace is available to Class Teachers only."},
                status=status.HTTP_403_FORBIDDEN,
            )

        staff = _staff_for_user(request.user)
        year, term = _current_period()
        streams = AcademicClassStream.objects.none()
        if staff:
            streams = AcademicClassStream.objects.select_related(
                "academic_class__Class", "academic_class__academic_year", "academic_class__term", "stream"
            ).filter(class_teacher=staff)
            if year:
                streams = streams.filter(academic_class__academic_year=year)
            if term:
                streams = streams.filter(academic_class__term=term)
            streams = streams.order_by("academic_class__Class__name", "stream__stream")

        stream_rows = list(streams)
        stream_ids = [row.pk for row in stream_rows]
        class_ids = sorted({row.academic_class_id for row in stream_rows})
        registers = list(
            ClassRegister.objects.filter(
                academic_class_stream_id__in=stream_ids,
                student__is_active=True,
            ).select_related(
                "student", "academic_class_stream__academic_class__Class", "academic_class_stream__stream"
            ).order_by("student__student_name", "student__reg_no")
        )

        # A learner should be shown once even if historical data happens to
        # contain duplicate register rows across streams.
        register_by_student = {}
        for register in registers:
            register_by_student.setdefault(register.student_id, register)
        student_ids = list(register_by_student)
        today = timezone.localdate()

        attendance_by_student: dict[int, list[str]] = defaultdict(list)
        attendance_totals: dict[int, dict[str, int]] = defaultdict(lambda: {"marked": 0, "present": 0})
        attendance_records = AttendanceRecord.objects.filter(
            student_id__in=student_ids,
            session__class_stream_id__in=stream_ids,
            session__date__lte=today,
        ).select_related("session")
        if year:
            attendance_records = attendance_records.filter(session__academic_year=year)
        if term:
            attendance_records = attendance_records.filter(session__term=term)
        for record in attendance_records:
            if record.status == AttendanceStatus.UNMARKED:
                continue
            totals = attendance_totals[record.student_id]
            totals["marked"] += 1
            if record.status in {AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.EXCUSED}:
                totals["present"] += 1
            if record.session.date == today:
                attendance_by_student[record.student_id].append(record.status)

        assessment_counts = {
            row["academic_class_id"]: row["total"]
            for row in Assessment.objects.filter(academic_class_id__in=class_ids)
            .values("academic_class_id")
            .annotate(total=Count("id"))
        }
        entered_counts: dict[tuple[int, int], int] = defaultdict(int)
        result_percentages: dict[tuple[int, int], list[Decimal]] = defaultdict(list)
        for result in Result.objects.filter(
            student_id__in=student_ids,
            assessment__academic_class_id__in=class_ids,
        ).select_related("assessment"):
            key = (result.student_id, result.assessment.academic_class_id)
            entered_counts[key] += 1
            if result.status == "VERIFIED":
                percentage = _percentage(result.score, result.assessment.out_of)
                if percentage is not None:
                    result_percentages[key].append(percentage)

        remarks = ReportCycleRemark.objects.filter(
            student_id__in=student_ids,
            academic_class_id__in=class_ids,
        ).only("student_id", "academic_class_id", "scope_key", "class_teacher_remark", "class_teacher_submitted_at")
        scope_keys = {class_id: _report_scope_key(class_id) for class_id in class_ids}
        remarks_by_key = {
            (row.student_id, row.academic_class_id): row
            for row in remarks
            if row.scope_key == scope_keys.get(row.academic_class_id)
        }

        students = []
        missing_marks = 0
        missing_remarks = 0
        marked_today = 0
        present_today = 0
        for student_id, register in register_by_student.items():
            student = register.student
            class_id = register.academic_class_stream.academic_class_id
            expected_marks = assessment_counts.get(class_id, 0)
            result_key = (student_id, class_id)
            missing_for_student = max(expected_marks - entered_counts.get(result_key, 0), 0)
            missing_marks += missing_for_student
            remark = remarks_by_key.get((student_id, class_id))
            remark_complete = bool(remark and remark.class_teacher_remark.strip())
            if expected_marks and not remark_complete:
                missing_remarks += 1
            attendance = attendance_totals.get(student_id, {"marked": 0, "present": 0})
            attendance_percent = round(attendance["present"] * 100 / attendance["marked"]) if attendance["marked"] else None
            average_values = result_percentages.get(result_key, [])
            average = (
                Decimal(sum(average_values) / len(average_values)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
                if average_values else None
            )
            today_status = _status_label(attendance_by_student.get(student_id, []))
            if today_status != "Not marked":
                marked_today += 1
                if today_status != "Absent":
                    present_today += 1
            stream = register.academic_class_stream
            students.append({
                "id": student.pk,
                "name": student.student_name,
                "admission_no": student.reg_no or f"ST{student.pk:04d}",
                "photo": _safe_file_url(student.photo),
                "class_stream_id": stream.pk,
                "class": str(stream.academic_class.Class),
                "stream": str(stream.stream),
                "attendance_status": today_status,
                "attendance_percent": attendance_percent,
                "average": f"{average}%" if average is not None else "—",
                "missing_marks": missing_for_student,
                "remark_status": "Submitted" if remark and remark.class_teacher_submitted_at else ("Draft" if remark_complete else "Needed"),
            })

        today_lessons = Timetable.objects.filter(
            class_stream_id__in=stream_ids,
            weekday=WEEKDAY_CODES[today.weekday()],
        ).select_related("class_stream__academic_class__Class", "class_stream__stream", "subject", "teacher", "time_slot", "classroom").order_by("time_slot__start_time")[:12]
        timetable = [{
            "id": lesson.pk,
            "time": str(lesson.time_slot),
            "subject": str(lesson.subject),
            "class": str(lesson.class_stream.academic_class.Class),
            "stream": str(lesson.class_stream.stream),
            "teacher": str(lesson.teacher or "Unassigned"),
            "room": str(lesson.classroom or "Room not set"),
        } for lesson in today_lessons]

        upcoming = Assessment.objects.filter(
            academic_class_id__in=class_ids,
            date__gte=today,
        ).select_related("academic_class__Class", "assessment_type", "subject").order_by("date", "subject__name")[:5]

        return Response({
            "title": "My Class",
            "description": "One practical workspace for your assigned learners, attendance follow-up, marks and report-card readiness.",
            "date": today.isoformat(),
            "assigned_classes": [{
                "id": stream.pk,
                "label": f"{stream.academic_class.Class} · {stream.stream}",
                "students": sum(1 for row in students if row["class_stream_id"] == stream.pk),
            } for stream in stream_rows],
            "metrics": [
                {"label": "My learners", "value": len(students), "hint": "Active learners on your register", "tone": "green"},
                {"label": "Attendance today", "value": f"{present_today}/{len(students)}", "hint": f"{marked_today} learner(s) marked today", "tone": "blue"},
                {"label": "Marks to follow up", "value": missing_marks, "hint": "Expected marks not yet entered", "tone": "gold"},
                {"label": "Remarks needed", "value": missing_remarks, "hint": "Learners without a class remark", "tone": "violet"},
            ],
            "students": students,
            "timetable": timetable,
            "upcoming_assessments": [{
                "id": row.pk,
                "date": row.date.isoformat(),
                "class": str(row.academic_class.Class),
                "subject": str(row.subject),
                "assessment": str(row.assessment_type),
                "out_of": row.out_of,
            } for row in upcoming],
        })
