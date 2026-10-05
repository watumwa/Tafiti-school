from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django import forms
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.http import QueryDict

from app.forms.admissions import AdmissionApplicationForm
from app.forms.classes import AcademicClassForm
from app.forms.school_settings import SchoolSettingForm
from app.forms.staff import StaffForm
from app.forms.student import StudentForm
from app.forms.subjects import SubjectForm
from app.models import (
    AcademicClass,
    AcademicClassStream,
    AdmissionApplication,
    SchoolSetting,
    Staff,
    Student,
    Subject,
)
from app.models.school_settings import AcademicYear
from app.models.students import find_duplicate_student
from app.selectors.school_settings import get_current_academic_year
from app.selectors.classes import get_current_term
from app.services.level_scope import bind_form_level_querysets, get_level_academic_classes_queryset, get_level_subjects_queryset
from app.services.school_level import get_active_school_level
from app.services.students import register_student

from .auth import canonical_role_label


@dataclass(frozen=True)
class ResourceFormConfig:
    model: type
    form_class: type[forms.ModelForm]
    create_roles: frozenset[str]
    edit_roles: frozenset[str]
    delete_roles: frozenset[str]
    create_label: str
    edit_label: str = "Edit"
    delete_label: str = "Delete"
    bind_level: bool = False
    allow_create: bool = True
    allow_delete: bool = True


ADMIN = frozenset({"Admin"})
ACADEMIC_MANAGERS = frozenset({"Admin", "Director of Studies"})
ADMISSION_MANAGERS = frozenset({"Admin", "Admissions Officer"})

RESOURCE_FORMS: dict[str, ResourceFormConfig] = {
    "students": ResourceFormConfig(
        model=Student,
        form_class=StudentForm,
        create_roles=ADMIN,
        edit_roles=ADMIN,
        delete_roles=ADMIN,
        create_label="Add student",
        delete_label="Deactivate",
        bind_level=True,
    ),
    "staff": ResourceFormConfig(
        model=Staff,
        form_class=StaffForm,
        create_roles=ADMIN,
        edit_roles=ADMIN,
        delete_roles=ADMIN,
        create_label="Add staff member",
        delete_label="Retire",
    ),
    "admissions": ResourceFormConfig(
        model=AdmissionApplication,
        form_class=AdmissionApplicationForm,
        create_roles=ADMISSION_MANAGERS,
        edit_roles=ADMISSION_MANAGERS,
        delete_roles=frozenset(),
        create_label="New application",
        allow_delete=False,
    ),
    "classes": ResourceFormConfig(
        model=AcademicClass,
        form_class=AcademicClassForm,
        create_roles=ACADEMIC_MANAGERS,
        edit_roles=ACADEMIC_MANAGERS,
        delete_roles=ACADEMIC_MANAGERS,
        create_label="Add academic class",
        bind_level=True,
    ),
    "subjects": ResourceFormConfig(
        model=Subject,
        form_class=SubjectForm,
        create_roles=ACADEMIC_MANAGERS,
        edit_roles=ACADEMIC_MANAGERS,
        delete_roles=ACADEMIC_MANAGERS,
        create_label="Add subject",
        bind_level=True,
    ),
    "settings": ResourceFormConfig(
        model=SchoolSetting,
        form_class=SchoolSettingForm,
        create_roles=frozenset(),
        edit_roles=ADMIN,
        delete_roles=frozenset(),
        create_label="Add settings",
        edit_label="Edit school settings",
        allow_create=False,
        allow_delete=False,
    ),
}


def _role_label(request) -> str:
    from .workspace import _active_role

    return canonical_role_label(_active_role(request))


def resource_action_policy(request, resource: str) -> dict[str, Any]:
    config = RESOURCE_FORMS.get(resource)
    if not config:
        return {
            "view": True,
            "create": False,
            "edit": False,
            "delete": False,
            "create_label": "Add record",
            "edit_label": "Edit",
            "delete_label": "Delete",
        }

    role = _role_label(request)
    superuser = bool(getattr(request.user, "is_superuser", False))
    can_create = config.allow_create and (superuser or role in config.create_roles)
    can_edit = superuser or role in config.edit_roles
    can_delete = config.allow_delete and (superuser or role in config.delete_roles)
    return {
        "view": True,
        "create": can_create,
        "edit": can_edit,
        "delete": can_delete,
        "create_label": config.create_label,
        "edit_label": config.edit_label,
        "delete_label": config.delete_label,
        "delete_mode": (
            "toggle-active" if resource == "students"
            else "toggle-status" if resource == "staff"
            else "delete"
        ),
    }


def _scoped_queryset(request, resource: str, config: ResourceFormConfig):
    if resource == "classes":
        return get_level_academic_classes_queryset(request=request)
    if resource == "subjects":
        return get_level_subjects_queryset(request=request)
    if resource == "settings":
        return SchoolSetting.objects.all()
    return config.model.objects.all()


def get_resource_instance(request, resource: str, pk: int):
    config = RESOURCE_FORMS.get(resource)
    if not config:
        raise KeyError(resource)
    return _scoped_queryset(request, resource, config).get(pk=pk)


def _build_form(request, resource: str, *, instance=None, data=None, files=None):
    config = RESOURCE_FORMS[resource]
    kwargs: dict[str, Any] = {"instance": instance}
    if data is not None:
        kwargs["data"] = data
    if files is not None:
        kwargs["files"] = files
    form = config.form_class(**kwargs)
    if config.bind_level:
        active_level = get_active_school_level(request)
        bind_form_level_querysets(form, active_level=active_level)
    return form


def _field_type(field: forms.Field) -> str:
    widget = field.widget
    if isinstance(field, forms.ModelMultipleChoiceField):
        return "multiselect"
    if isinstance(field, forms.ModelChoiceField):
        return "select"
    if isinstance(field, forms.BooleanField):
        return "checkbox"
    if isinstance(field, forms.DateTimeField):
        return "datetime-local"
    if isinstance(field, forms.DateField):
        return "date"
    if isinstance(field, forms.EmailField):
        return "email"
    if isinstance(field, (forms.IntegerField, forms.DecimalField, forms.FloatField)):
        return "number"
    if isinstance(field, forms.ImageField):
        return "image"
    if isinstance(field, forms.FileField):
        return "file"
    if isinstance(widget, forms.Textarea):
        return "textarea"
    if isinstance(field, forms.ChoiceField):
        return "select"
    return "text"


def _choice_options(field: forms.Field) -> list[dict[str, str]]:
    if isinstance(field, (forms.ModelChoiceField, forms.ModelMultipleChoiceField)):
        return [
            {"value": str(obj.pk), "label": str(obj)}
            for obj in field.queryset.all()[:500]
        ]
    if isinstance(field, forms.ChoiceField):
        options: list[dict[str, str]] = []
        for value, label in field.choices:
            if isinstance(label, (list, tuple)):
                continue
            options.append({"value": str(value), "label": str(label)})
        return options
    return []


def _serialize_initial(value: Any):
    if hasattr(value, "pk"):
        return str(value.pk)
    if isinstance(value, (list, tuple)):
        return [str(item.pk if hasattr(item, "pk") else item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def serialize_form(request, resource: str, *, instance=None) -> dict[str, Any]:
    form = _build_form(request, resource, instance=instance)
    fields = []
    for name, field in form.fields.items():
        field_type = _field_type(field)
        if field_type in {"file", "image"}:
            current_file_url = ""
            if instance is not None:
                try:
                    current_value = getattr(instance, name, None)
                    current_file_url = current_value.url if current_value else ""
                except Exception:
                    current_file_url = ""
            fields.append({
                "name": name,
                "label": field.label or name.replace("_", " ").title(),
                "type": field_type,
                "required": bool(field.required and instance is None),
                "disabled": False,
                "help_text": str(field.help_text or (
                    "Choose a clear JPG, PNG or WebP image. Upload a replacement only when you want to change the current photo."
                    if field_type == "image"
                    else "Upload a replacement file only when you want to change the existing one."
                )),
                "options": [],
                "initial": "",
                "current_file_url": current_file_url,
            })
            continue

        initial = form.initial.get(name, field.initial)
        if callable(initial):
            initial = initial()
        fields.append({
            "name": name,
            "label": field.label or name.replace("_", " ").title(),
            "type": field_type,
            "required": bool(field.required),
            "disabled": bool(field.disabled),
            "help_text": str(field.help_text or ""),
            "options": _choice_options(field),
            "initial": _serialize_initial(initial),
            "min_value": getattr(field, "min_value", None),
            "max_value": getattr(field, "max_value", None),
        })

    config = RESOURCE_FORMS[resource]
    return {
        "resource": resource,
        "mode": "edit" if instance is not None else "create",
        "title": config.edit_label if instance is not None else config.create_label,
        "submit_label": "Save changes" if instance is not None else config.create_label,
        "fields": fields,
    }


def _payload_to_querydict(payload: dict[str, Any]) -> QueryDict:
    data = QueryDict("", mutable=True)
    for key, value in payload.items():
        if isinstance(value, list):
            data.setlist(key, [str(item) for item in value])
        elif isinstance(value, bool):
            # Django BooleanField accepts true/false strings; ensure false is
            # explicit rather than omitted.
            data[key] = "true" if value else "false"
        elif value is None:
            data[key] = ""
        else:
            data[key] = str(value)
    return data


def _form_errors(form: forms.Form) -> dict[str, list[str]]:
    return {key: [str(item) for item in errors] for key, errors in form.errors.items()}


def save_resource_form(request, resource: str, payload, *, instance=None, files=None):
    config = RESOURCE_FORMS[resource]
    if isinstance(payload, QueryDict):
        form_data = payload
    else:
        form_data = _payload_to_querydict(dict(payload))
    form = _build_form(request, resource, instance=instance, data=form_data, files=files)
    if not form.is_valid():
        return None, _form_errors(form)

    if resource == "students" and instance is None:
        current_academic_year = get_current_academic_year()
        if not current_academic_year:
            return None, {"__all__": ["No current academic year is configured."]}
        try:
            current_term = get_current_term()
        except Exception:
            return None, {"__all__": ["No current term is configured."]}

        selected_class = form.cleaned_data.get("current_class")
        stream = form.cleaned_data.get("stream")
        academic_class = AcademicClass.objects.filter(
            academic_year=current_academic_year,
            Class=selected_class,
            term=current_term,
        ).first()
        if not academic_class:
            return None, {"current_class": ["Create the Academic Class for the current year and term first."]}
        if not AcademicClassStream.objects.filter(academic_class=academic_class, stream=stream).exists():
            return None, {"stream": ["This stream has not been configured for the selected academic class."]}

        try:
            with transaction.atomic():
                AcademicYear.objects.select_for_update().get(pk=current_academic_year.pk)
                duplicate = find_duplicate_student(
                    student_name=form.cleaned_data.get("student_name"),
                    birthdate=form.cleaned_data.get("birthdate"),
                    contact=form.cleaned_data.get("contact"),
                )
                if duplicate:
                    return None, {"__all__": [f"This student is already registered as {duplicate.reg_no}."]}
                student = form.save(commit=False)
                student.academic_year = current_academic_year
                student.term = current_term
                student.save()
                register_student(student, selected_class, stream)
                return student, {}
        except IntegrityError:
            return None, {"__all__": ["A conflicting student record already exists."]}

    try:
        saved = form.save()
        return saved, {}
    except (IntegrityError, ValueError) as exc:
        return None, {"__all__": [str(exc) or "The record could not be saved."]}


def _has_related_records(instance) -> bool:
    for relation in instance._meta.related_objects:
        accessor = relation.get_accessor_name()
        if not accessor:
            continue
        try:
            related = getattr(instance, accessor)
            if hasattr(related, "exists") and related.exists():
                return True
            if related is not None and not hasattr(related, "exists"):
                return True
        except Exception:
            continue
    return False


def delete_resource(request, resource: str, instance) -> dict[str, Any]:
    if resource == "students":
        instance.is_active = not instance.is_active
        instance.save(update_fields=["is_active"])
        return {
            "detail": "Student reactivated successfully." if instance.is_active else "Student deactivated successfully.",
            "status": "Active" if instance.is_active else "Inactive",
        }

    if resource == "staff":
        instance.staff_status = "Active" if instance.staff_status == "Retired" else "Retired"
        instance.save(update_fields=["staff_status"])
        return {
            "detail": "Staff member reactivated successfully." if instance.staff_status == "Active" else "Staff member retired successfully.",
            "status": instance.staff_status,
        }

    if _has_related_records(instance):
        return {"error": "This record has linked school data. Remove or reassign those dependencies before deleting it."}

    try:
        instance.delete()
        return {"detail": "Record deleted successfully."}
    except ProtectedError:
        return {"error": "This record is still referenced by other school data and cannot be deleted."}
