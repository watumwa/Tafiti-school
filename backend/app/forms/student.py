from django.forms import ModelForm, DateInput
from crispy_forms.helper import FormHelper

from django import forms
from django.core.exceptions import ValidationError
from app.models import AcademicClass, AcademicClassStream, Stream

from app.models.students import (
    Student,
    ClassRegister,
    StudentRegistrationCSV,
    find_duplicate_student,
)
from app.selectors.classes import get_current_term
from app.selectors.school_settings import get_current_academic_year
from app.validators import normalize_uganda_lin


class UgandaLinFormMixin:
    def clean_lin_number(self):
        value = normalize_uganda_lin(self.cleaned_data.get("lin_number"))
        if not value:
            return None

        existing = Student.objects.filter(lin_number__iexact=value)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("This LIN is already assigned to another student.")
        return value


def _current_academic_context():
    """Return the configured current year/term without making forms crash during setup."""
    year = get_current_academic_year()
    if not year:
        return None, None
    try:
        term = get_current_term()
    except Exception:
        term = None
    return year, term


def _current_academic_class(class_id):
    if not class_id:
        return None
    year, term = _current_academic_context()
    if not year or not term:
        return None
    return AcademicClass.objects.filter(
        academic_year=year,
        term=term,
        Class_id=class_id,
    ).first()


def _previous_streams_for_class(class_id, current_term):
    if not class_id or not current_term:
        return Stream.objects.none()
    return Stream.objects.filter(
        academicclassstream__academic_class__Class_id=class_id,
        academicclassstream__academic_class__term__start_date__lt=current_term.start_date,
    ).distinct().order_by("stream")


class StudentForm(UgandaLinFormMixin, ModelForm):

    class Meta:
        model = Student
        # A student's admission period is assigned from the configured current
        # academic year/term by the registration workflow. Asking users to
        # select it again allowed contradictory records to be submitted.
        exclude = ("reg_no", "academic_year", "term")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.Helper = FormHelper()
        self.fields["birthdate"].widget = DateInput(attrs={"type": "date"})

        # Stream is a master record, but a student may only be registered into
        # a stream attached to the selected AcademicClass for the current
        # academic year/term. Older forms exposed every global Stream, which
        # allowed a visually valid choice to fail only after Save.
        if "stream" in self.fields:
            selected_class_id = None
            if self.is_bound:
                selected_class_id = self.data.get("current_class")
            elif self.instance and self.instance.pk:
                selected_class_id = self.instance.current_class_id

            year, term = _current_academic_context()
            if selected_class_id and str(selected_class_id).isdigit() and year and term:
                academic_class = _current_academic_class(int(selected_class_id))
                if academic_class:
                    configured = Stream.objects.filter(
                        academicclassstream__academic_class=academic_class,
                    ).distinct().order_by("stream")
                    if configured.exists():
                        self.fields["stream"].queryset = configured
                    else:
                        # Legacy terms created before automatic rollover can
                        # have no AcademicClassStream links even though the
                        # same class/stream was configured in an earlier term.
                        self.fields["stream"].queryset = _previous_streams_for_class(
                            int(selected_class_id), term
                        )
            elif year and term:
                configured_current = Stream.objects.filter(
                    academicclassstream__academic_class__academic_year=year,
                    academicclassstream__academic_class__term=term,
                ).distinct().order_by("stream")
                if configured_current.exists():
                    self.fields["stream"].queryset = configured_current

    def clean(self):
        cleaned_data = super().clean()
        duplicate = find_duplicate_student(
            student_name=cleaned_data.get("student_name"),
            birthdate=cleaned_data.get("birthdate"),
            contact=cleaned_data.get("contact"),
            exclude_pk=self.instance.pk,
        )
        if duplicate:
            raise ValidationError(
                f"This student appears to already be registered as {duplicate.reg_no}. "
                "Open the existing record instead of creating another one."
            )
        return cleaned_data


class ClassScopedStudentForm(UgandaLinFormMixin, ModelForm):
    academic_class_stream = forms.ModelChoiceField(
        queryset=AcademicClassStream.objects.none(),
        label="Stream",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Student
        fields = (
            "student_name",
            "lin_number",
            "schoolpay_number",
            "residency_status",
            "gender",
            "birthdate",
            "nationality",
            "religion",
            "address",
            "guardian",
            "relationship",
            "contact",
            "photo",
        )

    def __init__(self, *args, academic_class=None, **kwargs):
        self.academic_class = academic_class
        super().__init__(*args, **kwargs)
        self.Helper = FormHelper()
        self.fields["birthdate"].widget = DateInput(attrs={"type": "date"})
        if academic_class is not None:
            self.fields["academic_class_stream"].queryset = (
                AcademicClassStream.objects.filter(academic_class=academic_class)
                .select_related("stream")
                .order_by("stream__stream")
            )

    def clean(self):
        cleaned_data = super().clean()
        duplicate = find_duplicate_student(
            student_name=cleaned_data.get("student_name"),
            birthdate=cleaned_data.get("birthdate"),
            contact=cleaned_data.get("contact"),
            exclude_pk=self.instance.pk,
        )
        if duplicate:
            raise ValidationError(
                f"This student appears to already be registered as {duplicate.reg_no}. "
                "Open the existing record instead of creating another one."
            )
        return cleaned_data


class StudentRegistrationCSVForm(ModelForm):
    class Meta:
        model = StudentRegistrationCSV
        fields = ("file_name",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.Helper = FormHelper()


class ClassRegisterForm(ModelForm):

    class Meta:
        model = ClassRegister
        fields = ("__all__")


class BulkStudentRegistrationForm(forms.Form):
    academic_class_stream = forms.ModelChoiceField(
        queryset=AcademicClassStream.objects.all(),
        label="Class Stream",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    student_ids = forms.CharField(
        label="Reg. Nos. (comma-separated)",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def clean_student_ids(self):
        ids = self.cleaned_data["student_ids"]
        student_ids = [id.strip() for id in ids.split(",") if id.strip()]
        valid_students = Student.objects.filter(reg_no__in=student_ids, is_active=True)
        if not valid_students.exists():
            raise forms.ValidationError("None of the registration numbers are valid.")
        return valid_students
