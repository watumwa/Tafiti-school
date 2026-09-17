from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


class SecondarySubjectResult(models.Model):
    student = models.ForeignKey(
        "app.Student",
        on_delete=models.CASCADE,
        related_name="subject_results",
    )
    academic_class = models.ForeignKey(
        "app.AcademicClass",
        on_delete=models.CASCADE,
        related_name="subject_results",
    )
    subject = models.ForeignKey(
        "app.Subject",
        on_delete=models.CASCADE,
        related_name="subject_results",
    )

    ca_average = models.DecimalField(max_digits=5, decimal_places=2)
    exam_score = models.DecimalField(max_digits=5, decimal_places=2)
    final_score = models.DecimalField(max_digits=5, decimal_places=2)

    grade = models.CharField(max_length=5)
    descriptor = models.CharField(max_length=120, blank=True)
    is_best_8 = models.BooleanField(default=False)

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "academic_class", "subject")
        ordering = ["-final_score"]
        db_table = "app_secondarysubjectresult"

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.final_score})"

    def clean(self):
        for field_name in ("ca_average", "exam_score", "final_score"):
            value = getattr(self, field_name)
            if value < 0 or value > 100:
                raise ValidationError({field_name: "Score must be between 0 and 100."})

        if self.subject_id and self.academic_class_id:
            if self.subject.section_id != self.academic_class.section_id:
                raise ValidationError("Subject section must match academic class section.")


class SecondaryOverallResult(models.Model):
    student = models.ForeignKey(
        "app.Student",
        on_delete=models.CASCADE,
        related_name="overall_results",
    )
    academic_class = models.ForeignKey(
        "app.AcademicClass",
        on_delete=models.CASCADE,
        related_name="overall_results",
    )

    overall_average = models.DecimalField(max_digits=5, decimal_places=2)
    best_8_average = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    total_subjects = models.PositiveSmallIntegerField(default=0)
    total_points = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))

    position = models.PositiveIntegerField(null=True, blank=True)
    qualifies_for_certificate = models.BooleanField(default=False)

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("student", "academic_class")
        db_table = "app_secondaryoverallresult"

    def __str__(self):
        return f"{self.student} - Overall ({self.overall_average})"

    def clean(self):
        if self.overall_average < 0 or self.overall_average > 100:
            raise ValidationError({"overall_average": "Overall average must be between 0 and 100."})

        if self.best_8_average is not None and (self.best_8_average < 0 or self.best_8_average > 100):
            raise ValidationError({"best_8_average": "Best 8 average must be between 0 and 100."})
