from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class ALevelCompetencyScale(models.Model):
    policy = models.ForeignKey(
        "secondary.SecondaryComputationPolicy",
        on_delete=models.CASCADE,
        related_name="alevel_scales",
    )
    code = models.CharField(max_length=10)
    descriptor = models.CharField(max_length=120)
    point_value = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    min_weighted_point = models.DecimalField(max_digits=6, decimal_places=2)
    max_weighted_point = models.DecimalField(max_digits=6, decimal_places=2)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "-min_weighted_point"]
        unique_together = ("policy", "code")
        db_table = "app_alevelcompetencyscale"

    def __str__(self):
        return f"{self.code} - {self.descriptor}"

    def clean(self):
        if self.min_weighted_point > self.max_weighted_point:
            raise ValidationError("Minimum weighted point cannot exceed the maximum weighted point.")
        if not self.policy_id:
            return
        if self.policy.level != self.policy.Level.UPPER_SECONDARY:
            raise ValidationError("A-Level competency scales must belong to an A-Level policy.")

        overlaps = (
            ALevelCompetencyScale.objects.filter(policy=self.policy)
            .exclude(pk=self.pk)
            .filter(
                min_weighted_point__lte=self.max_weighted_point,
                max_weighted_point__gte=self.min_weighted_point,
            )
        )
        if overlaps.exists():
            raise ValidationError("Competency scale overlaps with an existing range in this policy.")


class ALevelComponentWeight(models.Model):
    class ComponentType(models.TextChoices):
        COURSEWORK = "COURSEWORK", "Coursework / SBA"
        PRACTICAL = "PRACTICAL", "Practical"
        PROJECT = "PROJECT", "Project"
        WRITTEN_EXAM = "WRITTEN_EXAM", "Written Exam"
        ORAL = "ORAL", "Oral"
        MODULAR_EXAM = "MODULAR_EXAM", "Modular Exam"
        OTHER = "OTHER", "Other"

    policy = models.ForeignKey(
        "secondary.SecondaryComputationPolicy",
        on_delete=models.CASCADE,
        related_name="alevel_component_weights",
    )
    subject = models.ForeignKey(
        "app.Subject",
        on_delete=models.CASCADE,
        related_name="alevel_component_weights",
    )
    component_type = models.CharField(max_length=30, choices=ComponentType.choices)
    weight = models.DecimalField(max_digits=5, decimal_places=2)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ["subject__name", "component_type"]
        unique_together = ("policy", "subject", "component_type")
        db_table = "app_alevelcomponentweight"

    def __str__(self):
        return f"{self.subject} - {self.get_component_type_display()} ({self.weight}%)"

    def clean(self):
        if self.weight <= 0 or self.weight > 100:
            raise ValidationError({"weight": "Component weight must be greater than 0 and not exceed 100."})

        if not self.policy_id or not self.subject_id:
            return

        if self.policy.level != self.policy.Level.UPPER_SECONDARY:
            raise ValidationError("A-Level component weights must belong to an A-Level policy.")
        if self.policy.section_id != self.subject.section_id:
            raise ValidationError("Subject section must match the selected A-Level policy section.")

        existing_total = (
            ALevelComponentWeight.objects.filter(policy=self.policy, subject=self.subject)
            .exclude(pk=self.pk)
            .aggregate(total=Sum("weight"))
            .get("total")
            or Decimal("0.00")
        )
        if existing_total + (self.weight or Decimal("0.00")) > Decimal("100.00"):
            raise ValidationError("Total component weight for this subject cannot exceed 100.")


class ALevelSubjectModule(models.Model):
    subject = models.ForeignKey(
        "app.Subject",
        on_delete=models.CASCADE,
        related_name="alevel_modules",
    )
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=120)
    module_order = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["subject__name", "module_order", "code"]
        unique_together = ("subject", "code")
        db_table = "app_alevelsubjectmodule"

    def __str__(self):
        return f"{self.subject} - {self.code}"


class ALevelAssessmentRecord(models.Model):
    student = models.ForeignKey(
        "app.Student",
        on_delete=models.CASCADE,
        related_name="alevel_assessments",
    )
    subject = models.ForeignKey(
        "app.Subject",
        on_delete=models.CASCADE,
        related_name="alevel_assessments",
    )
    academic_year = models.ForeignKey(
        "app.AcademicYear",
        on_delete=models.CASCADE,
        related_name="alevel_assessments",
    )
    component_type = models.CharField(
        max_length=30,
        choices=ALevelComponentWeight.ComponentType.choices,
    )
    module = models.ForeignKey(
        "secondary.ALevelSubjectModule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessments",
    )
    attempt_no = models.PositiveSmallIntegerField(default=1)
    competency_code = models.CharField(max_length=30, blank=True, default="")
    points_awarded = models.DecimalField(max_digits=6, decimal_places=2)
    assessed_on = models.DateField(default=timezone.now)
    remarks = models.TextField(blank=True, default="")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alevel_assessments_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-assessed_on", "-id"]
        db_table = "app_alevelassessmentrecord"

    def __str__(self):
        return f"{self.student} - {self.subject} - {self.get_component_type_display()}"

    def clean(self):
        if self.points_awarded < 0:
            raise ValidationError({"points_awarded": "Points awarded cannot be negative."})
        if self.subject_id and self.student_id and self.student.current_class_id:
            if self.student.current_class.section_id != self.subject.section_id:
                raise ValidationError("Student and subject must belong to the same section.")
        if self.module_id and self.module.subject_id != self.subject_id:
            raise ValidationError("Selected module does not belong to the chosen subject.")
        if self.academic_year_id and self.student_id and self.student.academic_year_id:
            if self.student.academic_year_id != self.academic_year_id:
                raise ValidationError("Assessment academic year must match the student's academic year.")
