from django.core.exceptions import ValidationError
from django.db import models

from app.models.students import ClassRegister


class StudentSubjectEnrollment(models.Model):
    academic_class = models.ForeignKey(
        "app.AcademicClass",
        on_delete=models.CASCADE,
        related_name="subject_enrollments",
    )
    student = models.ForeignKey(
        "app.Student",
        on_delete=models.CASCADE,
        related_name="secondary_subject_enrollments",
    )
    subject = models.ForeignKey(
        "app.Subject",
        on_delete=models.CASCADE,
        related_name="student_enrollments",
    )
    is_active = models.BooleanField(default=True)
    is_compulsory = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "app_studentsubjectenrollment"
        ordering = ["academic_class_id", "subject__name", "student__student_name"]
        unique_together = ("academic_class", "student", "subject")
        indexes = [
            models.Index(fields=["academic_class", "subject"], name="sse_class_subject_idx"),
            models.Index(fields=["student", "academic_class"], name="sse_student_class_idx"),
        ]

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.academic_class})"

    def clean(self):
        if self.academic_class_id and self.subject_id:
            if self.academic_class.section_id != self.subject.section_id:
                raise ValidationError("Subject section must match the academic class section.")

        if not self.academic_class_id or not self.student_id:
            return

        if ClassRegister.objects.filter(
            academic_class_stream__academic_class_id=self.academic_class_id,
            student_id=self.student_id,
        ).exists():
            return

        if self.student.current_class_id != self.academic_class.Class_id:
            raise ValidationError("Student is not registered in the selected academic class.")
