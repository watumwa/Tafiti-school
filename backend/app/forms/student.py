from django.forms import ModelForm, DateInput
from crispy_forms.helper import FormHelper

from django import forms
from django.core.exceptions import ValidationError
from app.models import  AcademicClassStream

from app.models.students import (
    Student,
    ClassRegister,
    StudentRegistrationCSV,
    find_duplicate_student,
)

class StudentForm(ModelForm):
    
    class Meta:
        model = Student
        # A student's admission period is assigned from the configured current
        # academic year/term by the registration workflow.  Asking users to
        # select it again allowed contradictory records to be submitted.
        exclude = ("reg_no", "academic_year", "term")
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.Helper = FormHelper()
        self.fields["birthdate"].widget = DateInput(attrs={
                    "type": "date",
                })

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


class ClassScopedStudentForm(ModelForm):
    academic_class_stream = forms.ModelChoiceField(
        queryset=AcademicClassStream.objects.none(),
        label="Stream",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Student
        fields = (
            "student_name",
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
