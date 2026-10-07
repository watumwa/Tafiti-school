from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django import forms
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.response import Response

from app.forms.classes import AcademicClassStreamForm, ClassSubjectAllocationForm, StreamForm
from app.forms.results import AssessmentForm, AssesmentTypeForm, GradingSystemForm
from app.models import (
    AcademicClassStream,
    AcademicYear,
    Assessment,
    AssessmentType,
    ClassSubjectAllocation,
    GradingSystem,
    Stream,
    Term,
)

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context
from .workspace_forms import (
    _choice_options,
    _field_type,
    _form_errors,
    _payload_to_querydict,
    _serialize_initial,
)


READ_ROLES = {"Admin", "Head Teacher", "Director of Studies", "Teacher", "Class Teacher"}
WRITE_ROLES = {"Admin", "Director of Studies"}


class AcademicYearWorkspaceForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ["academic_year", "is_current"]
        widgets = {
            "academic_year": forms.TextInput(attrs={"placeholder": "2026"}),
        }


class TermWorkspaceForm(forms.ModelForm):
    class Meta:
        model = Term
        fields = ["academic_year", "term", "start_date", "end_date", "is_current"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "Term end date cannot be earlier than the start date.")
        return cleaned


@dataclass(frozen=True)
class ToolConfig:
    model: type
    form_class: type[forms.ModelForm]
    title: str
    description: str
    create_label: str


TOOLS: dict[str, ToolConfig] = {
    "academic-years": ToolConfig(
        model=AcademicYear,
        form_class=AcademicYearWorkspaceForm,
        title="Academic Years",
        description="Create academic years and explicitly choose the one Tafiti should treat as current.",
        create_label="Add academic year",
    ),
    "terms": ToolConfig(
        model=Term,
        form_class=TermWorkspaceForm,
        title="Terms",
        description="Manage term dates and the current term inside each academic year.",
        create_label="Add term",
    ),
    "streams": ToolConfig(
        model=Stream,
        form_class=StreamForm,
        title="Streams",
        description="Reusable stream names used when building academic classes.",
        create_label="Add stream",
    ),
    "class-streams": ToolConfig(
        model=AcademicClassStream,
        form_class=AcademicClassStreamForm,
        title="Class & Stream Setup",
        description="Connect an academic class to a stream and assign its class teacher.",
        create_label="Add class stream",
    ),
    "subject-allocations": ToolConfig(
        model=ClassSubjectAllocation,
        form_class=ClassSubjectAllocationForm,
        title="Subject Allocations",
        description="Allocate subjects and subject teachers to configured class streams.",
        create_label="Add allocation",
    ),
    "assessments": ToolConfig(
        model=Assessment,
        form_class=AssessmentForm,
        title="Assessments",
        description="Assessment structure that drives mark entry and verification.",
        create_label="Create assessment",
    ),
    "assessment-types": ToolConfig(
        model=AssessmentType,
        form_class=AssesmentTypeForm,
        title="Assessment Types",
        description="Assessment stages and weighting used by the existing results engine.",
        create_label="Add assessment type",
    ),
    "grading": ToolConfig(
        model=GradingSystem,
        form_class=GradingSystemForm,
        title="Grading System",
        description="Score bands, grades and points used by existing result calculations.",
        create_label="Add grading band",
    ),
}


def _role(request) -> str:
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_read(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in READ_ROLES)


def _can_write(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in WRITE_ROLES)


def _configure_form(tool: str, form: forms.ModelForm) -> forms.ModelForm:
    if tool == "class-streams":
        field = form.fields.get("academic_class")
        if field:
            field.widget = forms.Select()
    if tool == "terms":
        year_field = form.fields.get("academic_year")
        if year_field:
            year_field.queryset = AcademicYear.objects.order_by("-academic_year", "-id")
    return form


def _form(tool: str, *, instance=None, data=None):
    config = TOOLS[tool]
    kwargs: dict[str, Any] = {"instance": instance}
    if data is not None:
        kwargs["data"] = data
    return _configure_form(tool, config.form_class(**kwargs))


def _serialize_form(tool: str, *, instance=None) -> dict[str, Any]:
    config = TOOLS[tool]
    form = _form(tool, instance=instance)
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
        "resource": f"academic-{tool}",
        "mode": "edit" if instance is not None else "create",
        "title": f"Edit {config.title.rstrip('s')}" if instance is not None else config.create_label,
        "submit_label": "Save changes" if instance is not None else config.create_label,
        "fields": fields,
        "actions": {
            "view": True,
            "create": _can_write_dummy,
            "edit": _can_write_dummy,
            "delete": False,
            "create_label": config.create_label,
            "edit_label": "Edit",
            "delete_label": "Delete",
        },
    }


_can_write_dummy = True


def _rows(tool: str) -> tuple[list[list[str]], list[dict[str, Any]]]:
    if tool == "academic-years":
        queryset = AcademicYear.objects.order_by("-academic_year", "-id")
        return [["academic_year", "Academic Year"], ["status", "Status"]], [
            {
                "id": row.pk,
                "academic_year": row.academic_year,
                "status": "Current" if row.is_current else "Historical",
            }
            for row in queryset[:500]
        ]
    if tool == "terms":
        queryset = Term.objects.select_related("academic_year").order_by(
            "-academic_year__academic_year", "term", "id"
        )
        return [["academic_year", "Academic Year"], ["term", "Term"], ["dates", "Dates"], ["status", "Status"]], [
            {
                "id": row.pk,
                "academic_year": str(row.academic_year),
                "term": row.get_term_display(),
                "dates": f"{row.start_date:%d %b %Y} – {row.end_date:%d %b %Y}",
                "status": "Current" if row.is_current else "Closed / Historical",
            }
            for row in queryset[:1000]
        ]
    if tool == "streams":
        queryset = Stream.objects.order_by("stream", "id")
        return [["stream", "Stream"]], [
            {"id": row.pk, "stream": str(row)} for row in queryset[:500]
        ]
    if tool == "class-streams":
        queryset = AcademicClassStream.objects.select_related(
            "academic_class__Class", "academic_class__academic_year", "academic_class__term", "stream", "class_teacher"
        ).order_by("-academic_class__academic_year__academic_year", "academic_class__Class__name", "stream__stream")
        return [["class", "Academic Class"], ["stream", "Stream"], ["teacher", "Class Teacher"]], [
            {
                "id": row.pk,
                "class": str(row.academic_class),
                "stream": str(row.stream),
                "teacher": str(row.class_teacher or "—"),
            }
            for row in queryset[:1000]
        ]
    if tool == "subject-allocations":
        queryset = ClassSubjectAllocation.objects.select_related(
            "academic_class_stream__academic_class__Class", "academic_class_stream__stream", "subject", "subject_teacher"
        ).order_by("academic_class_stream__academic_class__Class__name", "subject__name")
        return [["class", "Class / Stream"], ["subject", "Subject"], ["teacher", "Subject Teacher"], ["status", "Status"]], [
            {
                "id": row.pk,
                "class": str(row.academic_class_stream),
                "subject": str(row.subject),
                "teacher": str(row.subject_teacher or "—"),
                "status": "Active" if row.is_active else "Inactive",
            }
            for row in queryset[:1500]
        ]
    if tool == "assessments":
        queryset = Assessment.objects.select_related(
            "academic_class__Class", "academic_class__academic_year", "academic_class__term", "subject", "assessment_type"
        ).order_by("-date", "academic_class__Class__name", "subject__name")
        return [["class", "Class"], ["subject", "Subject"], ["type", "Assessment"], ["date", "Date"], ["out_of", "Out Of"], ["status", "Marks"]], [
            {
                "id": row.pk,
                "class": str(row.academic_class),
                "subject": str(row.subject),
                "type": row.assessment_type.name,
                "date": row.date.isoformat(),
                "out_of": row.out_of,
                "status": "Completed" if row.is_done else "Open",
            }
            for row in queryset[:1500]
        ]
    if tool == "assessment-types":
        queryset = AssessmentType.objects.order_by("name")
        return [["name", "Assessment Type"], ["weight", "Weight"]], [
            {"id": row.pk, "name": row.name, "weight": str(row.weight)} for row in queryset[:500]
        ]
    queryset = GradingSystem.objects.order_by("min_score", "max_score")
    return [["min", "Min Score"], ["max", "Max Score"], ["grade", "Grade"], ["points", "Points"]], [
        {
            "id": row.pk,
            "min": str(row.min_score),
            "max": str(row.max_score),
            "grade": row.grade,
            "points": str(row.points),
        }
        for row in queryset[:500]
    ]


class AcademicToolAPIView(WorkspaceBaseAPIView):
    def _config(self, request, tool: str):
        if not _can_read(request):
            return None, Response({"detail": "Your current role cannot access academic configuration."}, status=status.HTTP_403_FORBIDDEN)
        config = TOOLS.get(tool)
        if not config:
            return None, Response({"detail": "Academic tool not found."}, status=status.HTTP_404_NOT_FOUND)
        return config, None

    def get(self, request, tool: str, pk: int | None = None):
        config, failure = self._config(request, tool)
        if failure:
            return failure
        instance = None
        if pk is not None:
            try:
                instance = config.model.objects.get(pk=pk)
            except config.model.DoesNotExist:
                return Response({"detail": "Record not found."}, status=status.HTTP_404_NOT_FOUND)
            schema = _serialize_form(tool, instance=instance)
            schema["actions"]["create"] = _can_write(request)
            schema["actions"]["edit"] = _can_write(request)
            return Response(schema)

        columns, rows = _rows(tool)
        schema = _serialize_form(tool)
        schema["actions"]["create"] = _can_write(request)
        schema["actions"]["edit"] = _can_write(request)
        return Response({
            "tool": tool,
            "title": config.title,
            "description": config.description,
            "columns": [{"key": key, "label": label} for key, label in columns],
            "rows": rows,
            "can_write": _can_write(request),
            "create_label": config.create_label,
            "form": schema,
        })

    def post(self, request, tool: str, pk: int | None = None):
        config, failure = self._config(request, tool)
        if failure:
            return failure
        if not _can_write(request):
            return Response({"detail": "Your current role cannot change academic configuration."}, status=status.HTTP_403_FORBIDDEN)

        instance = None
        if pk is not None:
            try:
                instance = config.model.objects.get(pk=pk)
            except config.model.DoesNotExist:
                return Response({"detail": "Record not found."}, status=status.HTTP_404_NOT_FOUND)

        payload = request.data if hasattr(request.data, "get") else {}
        form_data = payload if hasattr(payload, "getlist") else _payload_to_querydict(dict(payload))
        form = _form(tool, instance=instance, data=form_data)
        if not form.is_valid():
            return Response({"detail": "Check the highlighted fields.", "errors": _form_errors(form)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                saved = form.save()
        except IntegrityError:
            return Response({"detail": "That academic configuration already exists or conflicts with an existing record."}, status=status.HTTP_409_CONFLICT)

        return Response({
            "detail": f"{config.title.rstrip('s')} {'updated' if instance is not None else 'created'} successfully.",
            "id": saved.pk,
        }, status=status.HTTP_200_OK if instance is not None else status.HTTP_201_CREATED)
