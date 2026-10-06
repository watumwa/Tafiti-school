from __future__ import annotations

from typing import Any

from django import forms
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.response import Response

from app.forms.classes import ClassPromotionForm
from app.forms.student import ClassScopedStudentForm
from app.models import AcademicClass, AcademicYear, AcademicClassStream, ClassRegister
from app.models.students import find_duplicate_student
from app.services.class_promotions import promote_students_to_academic_class
from app.services.level_scope import get_level_academic_classes_queryset
from app.services.students import create_student_bill

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context, _can_access
from .workspace_forms import (
    _choice_options,
    _field_type,
    _form_errors,
    _payload_to_querydict,
    _serialize_initial,
)


CLASS_MANAGERS = {"Admin", "Head Teacher", "Director of Studies"}
PROMOTION_MANAGERS = {"Admin", "Director of Studies"}


def _role(request) -> str:
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_register(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in CLASS_MANAGERS)


def _can_promote(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in PROMOTION_MANAGERS)


def _serialize_form(form: forms.Form, *, title: str, submit_label: str) -> dict[str, Any]:
    fields = []
    for name, field in form.fields.items():
        initial = form.initial.get(name, field.initial)
        if callable(initial):
            initial = initial()
        fields.append({
            "name": name,
            "label": field.label or name.replace("_", " ").title(),
            "type": _field_type(field),
            "required": bool(field.required),
            "disabled": bool(field.disabled),
            "help_text": str(field.help_text or ""),
            "options": _choice_options(field),
            "initial": _serialize_initial(initial),
            "min_value": getattr(field, "min_value", None),
            "max_value": getattr(field, "max_value", None),
        })
    return {
        "resource": "classes-workspace",
        "mode": "create",
        "title": title,
        "submit_label": submit_label,
        "fields": fields,
        "actions": {
            "view": True,
            "create": True,
            "edit": False,
            "delete": False,
            "create_label": submit_label,
            "edit_label": "Edit",
            "delete_label": "Delete",
        },
    }


class ClassesWorkspaceAPIView(WorkspaceBaseAPIView):
    def _academic_class(self, request, pk):
        return get_level_academic_classes_queryset(request=request).filter(pk=pk).first()

    def get(self, request, pk: int, action: str):
        if not _can_access(request, "classes"):
            return Response({"detail": "Your current role cannot access classes."}, status=status.HTTP_403_FORBIDDEN)
        academic_class = self._academic_class(request, pk)
        if academic_class is None:
            return Response({"detail": "Academic class not found."}, status=status.HTTP_404_NOT_FOUND)

        if action == "register-form":
            if not _can_register(request):
                return Response({"detail": "Your current role cannot register students in classes."}, status=status.HTTP_403_FORBIDDEN)
            form = ClassScopedStudentForm(academic_class=academic_class)
            return Response(_serialize_form(form, title=f"Register student in {academic_class.Class}", submit_label="Register student"))

        if action == "promotion-form":
            if not _can_promote(request):
                return Response({"detail": "Only Admin or Director of Studies can run class promotions."}, status=status.HTTP_403_FORBIDDEN)
            if not academic_class.term.is_current or str(academic_class.term.term) != "3":
                return Response({"detail": "Class promotion is enabled only when the current term is Term 3."}, status=status.HTTP_409_CONFLICT)
            form = ClassPromotionForm(
                source_academic_class=academic_class,
                target_queryset=get_level_academic_classes_queryset(request=request),
            )
            return Response(_serialize_form(form, title="Promote students", submit_label="Review and promote"))

        return Response({"detail": "Class workflow not found."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, pk: int, action: str):
        if not _can_access(request, "classes"):
            return Response({"detail": "Your current role cannot access classes."}, status=status.HTTP_403_FORBIDDEN)
        academic_class = self._academic_class(request, pk)
        if academic_class is None:
            return Response({"detail": "Academic class not found."}, status=status.HTTP_404_NOT_FOUND)
        payload = request.data if hasattr(request.data, "get") else {}
        form_data = payload if hasattr(payload, "getlist") else _payload_to_querydict(dict(payload))

        if action == "register":
            if not _can_register(request):
                return Response({"detail": "Your current role cannot register students in classes."}, status=status.HTTP_403_FORBIDDEN)
            form = ClassScopedStudentForm(
                form_data,
                request.FILES,
                academic_class=academic_class,
            )
            if not form.is_valid():
                return Response({"detail": "Check the highlighted fields.", "errors": _form_errors(form)}, status=status.HTTP_400_BAD_REQUEST)

            class_stream = form.cleaned_data["academic_class_stream"]
            if class_stream.academic_class_id != academic_class.pk:
                return Response({"detail": "Select a stream that belongs to this academic class."}, status=status.HTTP_400_BAD_REQUEST)

            try:
                with transaction.atomic():
                    AcademicYear.objects.select_for_update().get(pk=academic_class.academic_year_id)
                    duplicate = find_duplicate_student(
                        student_name=form.cleaned_data.get("student_name"),
                        birthdate=form.cleaned_data.get("birthdate"),
                        contact=form.cleaned_data.get("contact"),
                    )
                    if duplicate is not None:
                        return Response(
                            {"detail": f"This student is already registered as {duplicate.reg_no}. Open the existing student record instead."},
                            status=status.HTTP_409_CONFLICT,
                        )
                    student = form.save(commit=False)
                    student.academic_year = academic_class.academic_year
                    student.current_class = academic_class.Class
                    student.stream = class_stream.stream
                    student.term = academic_class.term
                    student.is_active = True
                    student.save()
                    ClassRegister.objects.get_or_create(
                        academic_class_stream=class_stream,
                        student=student,
                    )
                    create_student_bill(student, academic_class)
            except IntegrityError:
                duplicate = find_duplicate_student(
                    student_name=form.cleaned_data.get("student_name"),
                    birthdate=form.cleaned_data.get("birthdate"),
                    contact=form.cleaned_data.get("contact"),
                )
                if duplicate is not None:
                    return Response(
                        {"detail": f"This student is already registered as {duplicate.reg_no}. Open the existing student record instead."},
                        status=status.HTTP_409_CONFLICT,
                    )
                return Response({"detail": "A conflicting student record could not be registered."}, status=status.HTTP_409_CONFLICT)

            return Response(
                {"detail": f"{student.student_name} was registered in {academic_class.Class} · {class_stream.stream}."},
                status=status.HTTP_201_CREATED,
            )

        if action == "promote":
            if not _can_promote(request):
                return Response({"detail": "Only Admin or Director of Studies can run class promotions."}, status=status.HTTP_403_FORBIDDEN)
            if not academic_class.term.is_current or str(academic_class.term.term) != "3":
                return Response({"detail": "Class promotion is enabled only when the current term is Term 3."}, status=status.HTTP_409_CONFLICT)

            form = ClassPromotionForm(
                form_data,
                source_academic_class=academic_class,
                target_queryset=get_level_academic_classes_queryset(request=request),
            )
            if not form.is_valid():
                return Response({"detail": "Check the promotion options.", "errors": _form_errors(form)}, status=status.HTTP_400_BAD_REQUEST)

            try:
                outcome = promote_students_to_academic_class(
                    source_academic_class=academic_class,
                    target_academic_class=form.cleaned_data["target_academic_class"],
                    source_stream=form.cleaned_data.get("source_stream"),
                    active_students_only=bool(form.cleaned_data.get("active_students_only")),
                    promoted_by=request.user,
                )
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            if outcome.has_missing_streams:
                return Response(
                    {
                        "detail": "Promotion stopped. Add the missing stream(s) to the target class first.",
                        "missing_streams": list(outcome.missing_stream_names),
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if outcome.total_candidates == 0:
                return Response({"detail": "No matching students were found for promotion in the selected scope."}, status=status.HTTP_409_CONFLICT)

            target = form.cleaned_data["target_academic_class"]
            return Response({
                "detail": (
                    f"Promotion completed to {target.Class} · {target.term} ({target.academic_year}): "
                    f"{outcome.promoted_count} promoted, {outcome.already_registered_count} already registered."
                ),
                "promoted_count": outcome.promoted_count,
                "already_registered_count": outcome.already_registered_count,
                "skipped_inactive_count": outcome.skipped_inactive_count,
                "updated_student_snapshots": outcome.updated_student_snapshots,
            })

        return Response({"detail": "Class workflow not found."}, status=status.HTTP_404_NOT_FOUND)
