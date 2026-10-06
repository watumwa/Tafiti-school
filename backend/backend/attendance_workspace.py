from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.response import Response

from app.models import (
    AcademicClassStream,
    AcademicYear,
    AttendancePolicy,
    AttendanceRecord,
    AttendanceSession,
    AttendanceStatus,
    ClassRegister,
    Term,
    Timetable,
)
from app.models.timetables import WeekDay
from app.services.attendance import get_or_create_session, initialize_session_records

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _staff_for_user, _token_context


READ_ROLES = {"Admin", "Head Teacher", "Director of Studies", "Teacher", "Class Teacher"}
MANAGER_ROLES = {"Admin", "Head Teacher", "Director of Studies"}
WRITE_ROLES = READ_ROLES

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


def _can_read(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in READ_ROLES)


def _can_write(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in WRITE_ROLES)


def _is_manager(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in MANAGER_ROLES)


def _date(value) -> str:
    return value.isoformat() if value else ""


def _parse_day(raw: str | None, default: date | None = None) -> date:
    parsed = parse_date(str(raw or ""))
    return parsed or default or timezone.localdate()


def _current_period():
    year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.order_by("-academic_year", "-id").first()
    term = None
    if year:
        term = Term.objects.filter(academic_year=year, is_current=True).first()
        if not term:
            term = Term.objects.filter(academic_year=year).order_by("term", "id").first()
    return year, term


def _scope_lessons(request, queryset):
    role = _role(request)
    if role in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        return queryset.filter(teacher=staff) if staff else queryset.none()
    return queryset


def _scope_sessions(request, queryset):
    role = _role(request)
    if role in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        return queryset.filter(teacher=staff) if staff else queryset.none()
    return queryset


def _class_stream_options(request, year, term):
    queryset = AcademicClassStream.objects.select_related(
        "academic_class__Class", "academic_class__academic_year", "academic_class__term", "stream", "class_teacher"
    )
    if year:
        queryset = queryset.filter(academic_class__academic_year=year)
    if term:
        queryset = queryset.filter(academic_class__term=term)
    role = _role(request)
    if role in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        if not staff:
            return []
        queryset = queryset.filter(
            Q(class_teacher=staff) | Q(subjects__subject_teacher=staff, subjects__is_active=True)
        ).distinct()
    return [
        {
            "id": row.pk,
            "label": f"{row.academic_class.Class} · {row.stream}",
        }
        for row in queryset.order_by("academic_class__Class__name", "stream__stream")[:500]
    ]


def _session_counts(session: AttendanceSession | None) -> dict[str, int]:
    counts = {value: 0 for value, _ in AttendanceStatus.choices}
    if not session:
        return counts
    for row in session.records.values("status").annotate(total=Count("id")):
        counts[row["status"]] = row["total"]
    return counts


def _scheduled_rows(request, selected_date: date, year, term):
    weekday = WEEKDAY_CODES[selected_date.weekday()]
    lessons = Timetable.objects.select_related(
        "class_stream__academic_class__Class",
        "class_stream__academic_class__academic_year",
        "class_stream__academic_class__term",
        "class_stream__stream",
        "subject",
        "teacher",
        "time_slot",
        "classroom",
    ).filter(weekday=weekday)
    if year:
        lessons = lessons.filter(class_stream__academic_class__academic_year=year)
    if term:
        lessons = lessons.filter(class_stream__academic_class__term=term)
    lessons = _scope_lessons(request, lessons).order_by("time_slot__start_time", "class_stream__academic_class__Class__name")
    lessons = list(lessons[:1000])

    if not lessons:
        return []

    class_stream_ids = {row.class_stream_id for row in lessons}
    student_counts = {
        row["academic_class_stream_id"]: row["total"]
        for row in ClassRegister.objects.filter(academic_class_stream_id__in=class_stream_ids)
        .values("academic_class_stream_id")
        .annotate(total=Count("student_id"))
    }
    sessions = _scope_sessions(
        request,
        AttendanceSession.objects.select_related("teacher", "time_slot").filter(
            date=selected_date,
            class_stream_id__in=class_stream_ids,
        ).prefetch_related("records"),
    )
    by_key = {
        (session.class_stream_id, session.subject_id, session.time_slot_id): session
        for session in sessions
    }

    rows = []
    for lesson in lessons:
        session = by_key.get((lesson.class_stream_id, lesson.subject_id, lesson.time_slot_id))
        counts = _session_counts(session)
        total_students = student_counts.get(lesson.class_stream_id, 0)
        marked = total_students - counts.get(AttendanceStatus.UNMARKED, 0) if session else 0
        completion = round((marked / total_students) * 100) if total_students else 0
        rows.append({
            "lesson_id": lesson.pk,
            "session_id": session.pk if session else None,
            "date": selected_date.isoformat(),
            "time": str(lesson.time_slot),
            "class_stream_id": lesson.class_stream_id,
            "class": str(lesson.class_stream.academic_class.Class),
            "stream": str(lesson.class_stream.stream),
            "subject": str(lesson.subject),
            "teacher": str(lesson.teacher or "Unassigned"),
            "room": str(lesson.classroom or "—"),
            "students": total_students,
            "present": counts.get(AttendanceStatus.PRESENT, 0),
            "late": counts.get(AttendanceStatus.LATE, 0),
            "absent": counts.get(AttendanceStatus.ABSENT, 0),
            "excused": counts.get(AttendanceStatus.EXCUSED, 0),
            "completion": completion,
            "status": "Submitted" if session and session.is_locked else ("In progress" if session else "Not started"),
            "locked": bool(session and session.is_locked),
            "can_take": bool(lesson.teacher_id and _can_write(request)),
        })
    return rows


def _history_rows(request, *, date_from: date, date_to: date, class_stream_id: int | None, state: str, query: str):
    sessions = AttendanceSession.objects.select_related(
        "class_stream__academic_class__Class",
        "class_stream__stream",
        "subject",
        "teacher",
        "time_slot",
    ).prefetch_related("records").filter(date__gte=date_from, date__lte=date_to)
    sessions = _scope_sessions(request, sessions)
    if class_stream_id:
        sessions = sessions.filter(class_stream_id=class_stream_id)
    if state == "submitted":
        sessions = sessions.filter(is_locked=True)
    elif state == "open":
        sessions = sessions.filter(is_locked=False)
    if query:
        sessions = sessions.filter(
            Q(class_stream__academic_class__Class__name__icontains=query)
            | Q(class_stream__stream__stream__icontains=query)
            | Q(subject__name__icontains=query)
            | Q(teacher__first_name__icontains=query)
            | Q(teacher__last_name__icontains=query)
        )

    rows = []
    for session in sessions.order_by("-date", "-time_slot__start_time", "-id")[:2500]:
        counts = _session_counts(session)
        total = session.records.count()
        marked = total - counts.get(AttendanceStatus.UNMARKED, 0)
        rate = 0
        if marked:
            attended = (
                counts.get(AttendanceStatus.PRESENT, 0)
                + counts.get(AttendanceStatus.LATE, 0)
                + counts.get(AttendanceStatus.EXCUSED, 0)
            )
            rate = round((attended / marked) * 100)
        rows.append({
            "id": session.pk,
            "date": session.date.isoformat(),
            "time": str(session.time_slot or "—"),
            "class": str(session.class_stream.academic_class.Class),
            "stream": str(session.class_stream.stream),
            "subject": str(session.subject),
            "teacher": str(session.teacher),
            "present": counts.get(AttendanceStatus.PRESENT, 0),
            "late": counts.get(AttendanceStatus.LATE, 0),
            "absent": counts.get(AttendanceStatus.ABSENT, 0),
            "excused": counts.get(AttendanceStatus.EXCUSED, 0),
            "attendance_rate": rate,
            "status": "Submitted" if session.is_locked else "Open",
            "submitted_at": _date(session.submitted_at),
        })
    return rows


def _report_rows(request, *, date_from: date, date_to: date, class_stream_id: int | None):
    records = AttendanceRecord.objects.select_related(
        "student",
        "session__class_stream__academic_class__Class",
        "session__class_stream__stream",
        "session__teacher",
    ).filter(
        session__date__gte=date_from,
        session__date__lte=date_to,
    ).exclude(status=AttendanceStatus.UNMARKED)
    role = _role(request)
    if role in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        records = records.filter(session__teacher=staff) if staff else records.none()
    if class_stream_id:
        records = records.filter(session__class_stream_id=class_stream_id)

    grouped: dict[int, dict] = {}
    for record in records.order_by("student__student_name")[:10000]:
        row = grouped.setdefault(record.student_id, {
            "student_id": record.student.display_student_id,
            "student": record.student.student_name,
            "class": str(record.session.class_stream.academic_class.Class),
            "stream": str(record.session.class_stream.stream),
            "present": 0,
            "late": 0,
            "absent": 0,
            "excused": 0,
            "marked": 0,
        })
        row["marked"] += 1
        if record.status in row:
            row[record.status] += 1

    policy = AttendancePolicy.objects.first()
    minimum = policy.minimum_attendance_percent if policy else 75
    rows = []
    for row in grouped.values():
        attended = row["present"] + row["late"] + row["excused"]
        rate = round((attended / row["marked"]) * 100, 1) if row["marked"] else 0
        rows.append({
            **row,
            "attendance_rate": rate,
            "status": "Below minimum" if rate < minimum else "On track",
        })
    rows.sort(key=lambda item: (item["attendance_rate"], item["student"].casefold()))
    return rows, minimum


def _hub_payload(request):
    year, term = _current_period()
    view = str(request.query_params.get("view") or "today").lower()
    if view not in {"today", "take", "history", "reports"}:
        view = "today"

    selected_date = _parse_day(request.query_params.get("date"))
    default_from = term.start_date if term else selected_date - timedelta(days=30)
    default_to = min(term.end_date, selected_date) if term else selected_date
    date_from = _parse_day(request.query_params.get("date_from"), default_from)
    date_to = _parse_day(request.query_params.get("date_to"), default_to)
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    raw_stream = str(request.query_params.get("class_stream") or "")
    class_stream_id = int(raw_stream) if raw_stream.isdigit() else None
    state = str(request.query_params.get("state") or "all").lower()
    if state not in {"all", "open", "submitted"}:
        state = "all"
    query = str(request.query_params.get("q") or "").strip()

    scheduled = _scheduled_rows(request, selected_date, year, term)
    history = _history_rows(
        request,
        date_from=date_from,
        date_to=date_to,
        class_stream_id=class_stream_id,
        state=state,
        query=query,
    )
    reports, minimum = _report_rows(
        request,
        date_from=date_from,
        date_to=date_to,
        class_stream_id=class_stream_id,
    )

    today_sessions = [row for row in scheduled if row["session_id"]]
    submitted = sum(1 for row in today_sessions if row["locked"])
    open_sessions = sum(1 for row in today_sessions if not row["locked"])
    not_started = sum(1 for row in scheduled if not row["session_id"])
    today_absent = sum(row["absent"] for row in today_sessions)

    if view == "take":
        scheduled = [row for row in scheduled if not row["locked"]]

    return {
        "title": "Attendance",
        "description": "Open today's scheduled lesson, mark the full class register, save progress and submit once. Submitted attendance locks until an authorised administrator reopens it.",
        "view": view,
        "selected_date": selected_date.isoformat(),
        "academic_context": {
            "year": str(year or ""),
            "term": str(term or ""),
        },
        "metrics": [
            {"label": "Scheduled lessons", "value": len(_scheduled_rows(request, selected_date, year, term)), "hint": selected_date.strftime("%d %b %Y"), "tone": "blue"},
            {"label": "Submitted", "value": submitted, "hint": "Locked attendance sessions", "tone": "green"},
            {"label": "Open / pending", "value": open_sessions + not_started, "hint": f"{not_started} not started", "tone": "gold"},
            {"label": "Absent today", "value": today_absent, "hint": "Across started sessions", "tone": "violet"},
        ],
        "scheduled": scheduled,
        "history": history,
        "reports": reports,
        "report_minimum": minimum,
        "class_streams": _class_stream_options(request, year, term),
        "filters": {
            "date": selected_date.isoformat(),
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "class_stream": class_stream_id,
            "state": state,
            "q": query,
        },
        "actions": {
            "can_take": _can_write(request),
            "is_manager": _is_manager(request),
            "role": _role(request),
        },
    }


class AttendanceWorkspaceAPIView(WorkspaceBaseAPIView):
    def get(self, request, screen: str):
        if not _can_read(request):
            return Response(
                {"detail": "Your current role cannot access attendance."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if screen != "hub":
            return Response({"detail": "Unknown attendance screen."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_hub_payload(request))

    @transaction.atomic
    def post(self, request, screen: str):
        if not _can_write(request):
            return Response(
                {"detail": "Your current role cannot take attendance."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if screen != "hub":
            return Response({"detail": "Unknown attendance action."}, status=status.HTTP_404_NOT_FOUND)

        action = str(request.data.get("action") or "").strip().lower()
        if action != "start":
            return Response({"detail": "Unknown attendance action."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            lesson_id = int(request.data.get("lesson_id"))
        except (TypeError, ValueError):
            return Response({"detail": "Choose a scheduled lesson before taking attendance."}, status=status.HTTP_400_BAD_REQUEST)
        selected_date = _parse_day(request.data.get("date"))

        try:
            lesson = Timetable.objects.select_related(
                "class_stream__academic_class__academic_year",
                "class_stream__academic_class__term",
                "teacher",
                "subject",
                "time_slot",
            ).get(pk=lesson_id)
        except Timetable.DoesNotExist:
            return Response({"detail": "Scheduled lesson was not found."}, status=status.HTTP_404_NOT_FOUND)

        if lesson.weekday != WEEKDAY_CODES[selected_date.weekday()]:
            return Response(
                {"detail": "This lesson is not scheduled on the selected date."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not lesson.teacher_id:
            return Response(
                {"detail": "Assign a teacher to this timetable lesson before taking attendance."},
                status=status.HTTP_409_CONFLICT,
            )

        role = _role(request)
        if role in {"Teacher", "Class Teacher"}:
            staff = _staff_for_user(request.user)
            if not staff or lesson.teacher_id != staff.pk:
                return Response(
                    {"detail": "You can only take attendance for lessons assigned to you."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        academic_class = lesson.class_stream.academic_class
        term = academic_class.term
        if selected_date < term.start_date or selected_date > term.end_date:
            return Response(
                {"detail": "The selected date is outside this lesson's academic term."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = get_or_create_session(
            class_stream=lesson.class_stream,
            subject=lesson.subject,
            teacher=lesson.teacher,
            date=selected_date,
            time_slot=lesson.time_slot,
            academic_year=academic_class.academic_year,
            term=term,
            lesson=lesson,
        )
        initialize_session_records(session)
        return Response(
            {
                "detail": "Attendance register opened." if not session.is_locked else "Attendance register is already submitted.",
                "session_id": session.pk,
                "status": "Submitted" if session.is_locked else "Open",
            },
            status=status.HTTP_200_OK,
        )
