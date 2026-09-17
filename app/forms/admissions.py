from django import forms

from django.utils import timezone

from app.models import AcademicClass, AdmissionApplication, AdmissionCycle, Class, Stream
from app.models.students import normalize_guardian_contact, normalize_student_name


class AdmissionApplicationForm(forms.ModelForm):
    class Meta:
        model = AdmissionApplication
        fields = (
            "cycle", "student_name", "gender", "birthdate", "nationality", "religion",
            "address", "applying_class", "preferred_stream", "previous_school", "guardian",
            "relationship", "contact", "internal_notes",
        )
        widgets = {"birthdate": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["cycle"].queryset = AdmissionCycle.objects.filter(
            is_active=True, opens_on__lte=today, closes_on__gte=today,
        ).select_related("academic_year")
        self.fields["preferred_stream"].required = True


class PublicAdmissionApplicationForm(forms.ModelForm):
    privacy_consent = forms.BooleanField(
        label="I confirm that the information is correct and consent to the school using it for this application."
    )
    website = forms.CharField(required=False, widget=forms.HiddenInput, label="Leave blank")

    class Meta:
        model = AdmissionApplication
        fields = (
            "cycle", "student_name", "gender", "birthdate", "nationality", "religion",
            "address", "applying_class", "preferred_stream", "previous_school", "guardian",
            "relationship", "contact",
        )
        widgets = {"birthdate": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "student_name": "Learner's full name", "birthdate": "Learner's date of birth",
            "contact": "Guardian telephone number", "guardian": "Guardian's full name",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        open_cycles = AdmissionCycle.objects.filter(
            is_active=True, opens_on__lte=today, closes_on__gte=today,
        )
        configured = AcademicClass.objects.filter(academic_year__in=open_cycles.values("academic_year_id"))
        self.fields["cycle"].queryset = open_cycles.select_related("academic_year")
        self.fields["applying_class"].queryset = Class.objects.filter(
            id__in=configured.values("Class_id")
        ).distinct().order_by("name")
        self.fields["preferred_stream"].queryset = Stream.objects.filter(
            academicclassstream__academic_class__in=configured
        ).distinct().order_by("stream")
        self.fields["preferred_stream"].required = True

    def clean_website(self):
        value = self.cleaned_data.get("website", "")
        if value:
            raise forms.ValidationError("Unable to submit this application.")
        return value

    def clean(self):
        data = super().clean()
        cycle = data.get("cycle")
        name = normalize_student_name(data.get("student_name"))
        birthdate = data.get("birthdate")
        contact = normalize_guardian_contact(data.get("contact"))
        if cycle and name and birthdate and contact:
            possible = AdmissionApplication.objects.filter(cycle=cycle, birthdate=birthdate).exclude(
                status__in=(AdmissionApplication.STATUS_REJECTED, AdmissionApplication.STATUS_WITHDRAWN)
            )
            for application in possible.only("student_name", "contact"):
                if (
                    normalize_student_name(application.student_name) == name
                    and normalize_guardian_contact(application.contact) == contact
                ):
                    raise forms.ValidationError(
                        "An application for this learner already exists in this admission cycle. Use Track application or contact the school."
                    )
        return data


class PublicAdmissionTrackingForm(forms.Form):
    application_number = forms.CharField(max_length=30)
    contact = forms.CharField(max_length=50, label="Guardian telephone number")
