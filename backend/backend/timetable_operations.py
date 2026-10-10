from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from app.models import (
    AcademicClassStream,
    AcademicYear,
    BreakPeriod,
    ClassRegister,
    ClassSubjectAllocation,
    Classroom,
    Staff,
    Term,
    TimeSlot,
    Timetable,
)
from app.models.timetables import WeekDay

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _staff_for_user, _token_context


READ_ROLES = {"Admin", "Head Teacher", "Director of Studies", "Teacher", "Class Teacher"}
EDIT_ROLES = {"Admin", "Director of Studies"}
LOCK_ROLES = {"Admin", "Head Teacher"}


def _role(request):
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_read(request):
    return bool(request.user.is_superuser or _role(request) in READ_ROLES)


def _can_edit(request):
    return bool(request.user.is_superuser or _role(request) in EDIT_ROLES)


def _can_lock(request):
    return bool(request.user.is_superuser or _role(request) in LOCK_ROLES)


def _current_period():
    year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.order_by("-academic_year", "-id").first()
    term = None
    if year:
        term = Term.objects.filter(academic_year=year, is_current=True).first() or Term.objects.filter(academic_year=year).order_by("term", "id").first()
    return year, term


def _streams(request):
    year, term = _current_period()
    qs = AcademicClassStream.objects.select_related(
        "academic_class__Class", "academic_class__academic_year", "academic_class__term", "stream", "class_teacher"
    ).order_by("academic_class__Class__name", "stream__stream")
    if year:
        qs = qs.filter(academic_class__academic_year=year)
    if term:
        qs = qs.filter(academic_class__term=term)
    if _role(request) in {"Teacher", "Class Teacher"} and not request.user.is_superuser:
        staff = _staff_for_user(request.user)
        if not staff:
            return qs.none()
        allocated = ClassSubjectAllocation.objects.filter(subject_teacher=staff, is_active=True).values_list("academic_class_stream_id", flat=True)
        qs = qs.filter(pk__in=set(allocated) | set(qs.filter(class_teacher=staff).values_list("pk", flat=True)))
    return qs


def _entry(row):
    return {
        "id": row.pk,
        "weekday": row.weekday,
        "weekday_label": row.get_weekday_display(),
        "time_slot_id": row.time_slot_id,
        "time": str(row.time_slot),
        "subject": row.subject.name,
        "subject_id": row.subject_id,
        "teacher": str(row.teacher or "—"),
        "teacher_id": row.teacher_id,
        "classroom": str(row.classroom or "—"),
        "classroom_id": row.classroom_id,
        "class_stream_id": row.class_stream_id,
        "class_stream": f"{row.class_stream.academic_class.Class} · {row.class_stream.stream}",
    }


def _hub(request):
    streams = list(_streams(request)[:500])
    selected_id = str(request.query_params.get("class_stream") or "")
    selected = next((row for row in streams if str(row.pk) == selected_id), None) or (streams[0] if streams else None)
    slots = list(TimeSlot.objects.order_by("start_time", "end_time", "id"))
    breaks = list(BreakPeriod.objects.select_related("time_slot").order_by("weekday", "time_slot__start_time"))

    year, term = _current_period()
    # ``Timetable.teacher`` exposes its reverse relation as ``teaching_slots``.
    # Using the old relation name here makes the whole timetable workspace fail
    # before it can return any data.
    teacher_qs = Staff.objects.filter(staff_status="Active", teaching_slots__isnull=False)
    if year:
        teacher_qs = teacher_qs.filter(teaching_slots__class_stream__academic_class__academic_year=year)
    if term:
        teacher_qs = teacher_qs.filter(teaching_slots__class_stream__academic_class__term=term)
    if _role(request) in {"Teacher", "Class Teacher"} and not request.user.is_superuser:
        own_staff = _staff_for_user(request.user)
        teacher_qs = teacher_qs.filter(pk=own_staff.pk) if own_staff else teacher_qs.none()
    teachers = list(teacher_qs.distinct().order_by("first_name", "last_name")[:500])
    selected_teacher_id = str(request.query_params.get("teacher") or "")
    selected_teacher = next((row for row in teachers if str(row.pk) == selected_teacher_id), None)
    view_mode = "teacher" if selected_teacher else "class"

    entries = []
    allocations = []
    if view_mode == "teacher":
        entries = [
            _entry(row) for row in Timetable.objects.filter(teacher=selected_teacher).select_related(
                "time_slot", "subject", "teacher", "classroom", "class_stream__academic_class__Class", "class_stream__stream"
            ).filter(
                class_stream__academic_class__academic_year=year,
                class_stream__academic_class__term=term,
            ).order_by("weekday", "time_slot__start_time")
        ] if year and term else []
    elif selected:
        entries = [
            _entry(row) for row in Timetable.objects.filter(class_stream=selected).select_related(
                "time_slot", "subject", "teacher", "classroom", "class_stream__academic_class__Class", "class_stream__stream"
            ).order_by("weekday", "time_slot__start_time")
        ]
        allocations = [
            {
                "id": row.pk,
                "subject_id": row.subject_id,
                "subject": row.subject.name,
                "teacher_id": row.subject_teacher_id,
                "teacher": str(row.subject_teacher or "—"),
            }
            for row in ClassSubjectAllocation.objects.filter(
                academic_class_stream=selected, is_active=True
            ).select_related("subject", "subject_teacher").order_by("subject__name")
        ]

    scheduled = len(entries)
    possible = len(slots) * len(WeekDay.choices)
    selected_locked = bool(selected.is_timetable_locked) if selected and view_mode == "class" else False
    return {
        "title": "Timetable",
        "description": "Build, publish and print weekly class or teacher timetables with teacher, room, class and break conflict protection.",
        "role": _role(request),
        "view_mode": view_mode,
        "period": {
            "year": str((selected.academic_class.academic_year if selected else year) or ""),
            "term": str((selected.academic_class.term if selected else term) or ""),
        },
        "streams": [
            {
                "id": row.pk,
                "label": f"{row.academic_class.Class} · {row.stream}",
                "locked": bool(row.is_timetable_locked),
                "published": bool(row.is_timetable_locked),
                "students": ClassRegister.objects.filter(academic_class_stream=row).count(),
            }
            for row in streams
        ],
        "teachers": [{"id": row.pk, "label": str(row)} for row in teachers],
        "selected_stream_id": selected.pk if selected else None,
        "selected_teacher_id": selected_teacher.pk if selected_teacher else None,
        "selected_locked": selected_locked,
        "publication_state": "Published" if selected_locked else ("Teacher view" if view_mode == "teacher" else "Draft"),
        "weekdays": [{"value": value, "label": label} for value, label in WeekDay.choices],
        "time_slots": [{"id": row.pk, "label": str(row), "start": row.start_time.isoformat(), "end": row.end_time.isoformat()} for row in slots],
        "breaks": [{"weekday": row.weekday, "time_slot_id": row.time_slot_id, "name": row.name} for row in breaks],
        "entries": entries,
        "allocations": allocations,
        "classrooms": [{"id": row.pk, "label": str(row), "capacity": row.capacity} for row in Classroom.objects.order_by("name")[:500]],
        "metrics": [
            {"label": "Scheduled lessons", "value": scheduled, "hint": "For the selected timetable view", "tone": "blue"},
            {"label": "Allocated subjects", "value": len(allocations), "hint": "Available to schedule in class view", "tone": "violet"},
            {"label": "Open teaching cells", "value": max(possible - scheduled - len(breaks), 0), "hint": "Before school-specific non-teaching rules", "tone": "green"},
            {"label": "Status", "value": "Published" if selected_locked else ("Teacher" if view_mode == "teacher" else "Draft"), "hint": "Publication state", "tone": "gold"},
        ],
        "permissions": {"edit": _can_edit(request) and view_mode == "class", "lock": _can_lock(request) and view_mode == "class", "publish": _can_lock(request) and view_mode == "class"},
    }


def _errors(exc):
    if hasattr(exc, "message_dict"):
        return {key: [str(item) for item in value] for key, value in exc.message_dict.items()}
    return {"__all__": [str(item) for item in getattr(exc, "messages", [str(exc)])]}


class TimetableOperationsAPIView(WorkspaceBaseAPIView):
    def get(self, request, screen: str):
        if not _can_read(request):
            return Response({"detail": "Your current role cannot access the timetable."}, status=status.HTTP_403_FORBIDDEN)
        if screen == "hub":
            return Response(_hub(request))
        return Response({"detail": "Unknown timetable screen."}, status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    def post(self, request, screen: str):
        if screen != "hub":
            return Response({"detail": "Unknown timetable action."}, status=status.HTTP_404_NOT_FOUND)
        action = str(request.data.get("action") or "").strip().lower()
        stream_id = request.data.get("class_stream_id")
        try:
            class_stream = AcademicClassStream.objects.select_for_update().select_related("academic_class").get(pk=stream_id)
        except (AcademicClassStream.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Choose a valid class / stream."}, status=status.HTTP_400_BAD_REQUEST)

        if action in {"toggle_lock", "publish", "unpublish"}:
            if not _can_lock(request):
                return Response({"detail": "Only Admin or Head Teacher can publish, unpublish, lock or unlock timetables."}, status=status.HTTP_403_FORBIDDEN)
            if action == "publish" and not Timetable.objects.filter(class_stream=class_stream).exists():
                return Response({"detail": "Add at least one lesson before publishing this timetable."}, status=status.HTTP_409_CONFLICT)
            if action == "publish":
                class_stream.is_timetable_locked = True
                detail = "Timetable published and locked against accidental edits."
            elif action == "unpublish":
                class_stream.is_timetable_locked = False
                detail = "Timetable returned to draft and unlocked for editing."
            else:
                class_stream.is_timetable_locked = bool(request.data.get("locked"))
                detail = "Timetable lock status updated."
            class_stream.save(update_fields=["is_timetable_locked"])
            return Response({"detail": detail, "locked": class_stream.is_timetable_locked, "published": class_stream.is_timetable_locked})

        if not _can_edit(request):
            return Response({"detail": "Only Admin or Director of Studies can edit the timetable."}, status=status.HTTP_403_FORBIDDEN)
        if class_stream.is_timetable_locked:
            return Response({"detail": "This timetable is published and locked. Unpublish it before making changes."}, status=status.HTTP_409_CONFLICT)

        if action == "delete_entry":
            entry = Timetable.objects.filter(pk=request.data.get("entry_id"), class_stream=class_stream).first()
            if not entry:
                return Response({"detail": "Timetable entry was not found."}, status=status.HTTP_404_NOT_FOUND)
            entry.delete()
            return Response({"detail": "Lesson removed from the timetable."})

        if action == "save_entry":
            allocation = ClassSubjectAllocation.objects.filter(
                pk=request.data.get("allocation_id"), academic_class_stream=class_stream, is_active=True
            ).select_related("subject", "subject_teacher").first()
            if not allocation:
                return Response({"detail": "Choose an active subject allocation for this class."}, status=status.HTTP_400_BAD_REQUEST)
            slot = TimeSlot.objects.filter(pk=request.data.get("time_slot_id")).first()
            if not slot:
                return Response({"detail": "Choose a valid time slot."}, status=status.HTTP_400_BAD_REQUEST)
            weekday = str(request.data.get("weekday") or "").upper()
            if weekday not in {value for value, _ in WeekDay.choices}:
                return Response({"detail": "Choose a valid weekday."}, status=status.HTTP_400_BAD_REQUEST)
            classroom = Classroom.objects.filter(pk=request.data.get("classroom_id")).first() if request.data.get("classroom_id") else None
            entry_id = request.data.get("entry_id")
            entry = Timetable.objects.filter(pk=entry_id, class_stream=class_stream).first() if entry_id else Timetable(class_stream=class_stream)
            if entry_id and not entry:
                return Response({"detail": "Timetable entry was not found."}, status=status.HTTP_404_NOT_FOUND)
            entry.weekday = weekday
            entry.time_slot = slot
            entry.allocation = allocation
            entry.subject = allocation.subject
            entry.teacher = allocation.subject_teacher
            entry.classroom = classroom
            try:
                entry.save()
            except ValidationError as exc:
                return Response({"detail": "This lesson conflicts with the timetable rules.", "errors": _errors(exc)}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": "Lesson saved to the timetable.", "entry": _entry(entry)}, status=status.HTTP_201_CREATED if not entry_id else status.HTTP_200_OK)

        return Response({"detail": "Unknown timetable action."}, status=status.HTTP_400_BAD_REQUEST)
