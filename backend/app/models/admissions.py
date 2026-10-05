"""Applicant lifecycle models; enrolled students remain in the Student master."""
import uuid

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from app.constants import GENDERS, NATIONALITIES, RELIGIONS


class AdmissionCycle(models.Model):
    name = models.CharField(max_length=100)
    academic_year = models.ForeignKey("app.AcademicYear", on_delete=models.PROTECT)
    opens_on = models.DateField()
    closes_on = models.DateField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-opens_on",)
        constraints = [models.UniqueConstraint(fields=("name", "academic_year"), name="unique_admission_cycle_year")]

    def clean(self):
        super().clean()
        if self.closes_on < self.opens_on:
            raise ValidationError({"closes_on": "Closing date cannot be before opening date."})

    def __str__(self):
        return f"{self.name} - {self.academic_year}"


class AdmissionApplication(models.Model):
    SOURCE_INTERNAL = "internal"
    SOURCE_PUBLIC = "public"
    SOURCE_CHOICES = ((SOURCE_INTERNAL, "Internal"), (SOURCE_PUBLIC, "Online application"))
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_REVIEW = "review"
    STATUS_SHORTLISTED = "shortlisted"
    STATUS_ASSESSMENT = "assessment"
    STATUS_INTERVIEW = "interview"
    STATUS_WAITLISTED = "waitlisted"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_ENROLLED = "enrolled"
    STATUS_WITHDRAWN = "withdrawn"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Draft"), (STATUS_SUBMITTED, "Submitted"),
        (STATUS_REVIEW, "Under review"), (STATUS_SHORTLISTED, "Shortlisted"),
        (STATUS_ASSESSMENT, "Assessment"), (STATUS_INTERVIEW, "Interview"),
        (STATUS_WAITLISTED, "Wait-listed"), (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"), (STATUS_ENROLLED, "Enrolled"),
        (STATUS_WITHDRAWN, "Withdrawn"),
    )

    cycle = models.ForeignKey(AdmissionCycle, on_delete=models.PROTECT, related_name="applications")
    application_number = models.CharField(max_length=30, unique=True, editable=False)
    student_name = models.CharField(max_length=50)
    gender = models.CharField(max_length=2, choices=GENDERS)
    birthdate = models.DateField()
    nationality = models.CharField(max_length=30, choices=NATIONALITIES)
    religion = models.CharField(max_length=30, choices=RELIGIONS)
    address = models.CharField(max_length=150)
    applying_class = models.ForeignKey("app.Class", on_delete=models.PROTECT, related_name="admission_applications")
    preferred_stream = models.ForeignKey("app.Stream", null=True, blank=True, on_delete=models.SET_NULL)
    previous_school = models.CharField(max_length=150, blank=True)
    guardian = models.CharField(max_length=50)
    relationship = models.CharField(max_length=50)
    contact = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    internal_notes = models.TextField(blank=True)
    decision_notes = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_INTERNAL)
    privacy_consent_at = models.DateTimeField(null=True, blank=True)
    enrolled_student = models.OneToOneField(
        "app.Student", null=True, blank=True, on_delete=models.PROTECT,
        related_name="source_admission_application",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="created_admission_applications",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("cycle", "status"), name="admission_cycle_status_idx")]

    def clean(self):
        super().clean()
        errors = {}
        today = timezone.localdate()
        if self.birthdate and self.birthdate >= today:
            errors["birthdate"] = "Birth date must be before today."
        if self.cycle_id:
            if not self.cycle.is_active:
                errors["cycle"] = "The selected admission cycle is inactive."
            elif not self.cycle.opens_on <= today <= self.cycle.closes_on:
                errors["cycle"] = "The selected admission cycle is not currently open."
        if self.cycle_id and self.applying_class_id and self.preferred_stream_id:
            configured = models.Q(
                academic_class__Class_id=self.applying_class_id,
                academic_class__academic_year_id=self.cycle.academic_year_id,
                stream_id=self.preferred_stream_id,
            )
            if not apps.get_model("app", "AcademicClassStream").objects.filter(configured).exists():
                errors["preferred_stream"] = "This stream is not configured for the selected class and admission year."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.application_number:
            year = timezone.now().year
            self.application_number = f"APP-{year}-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.application_number} - {self.student_name}"


class AdmissionStatusHistory(models.Model):
    application = models.ForeignKey(AdmissionApplication, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    notes = models.TextField(blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-changed_at",)
