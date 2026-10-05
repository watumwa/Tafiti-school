from __future__ import annotations

from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import models


# Keep the API attached to the project's established Django accounts.  The
# school database and the legacy app's foreign keys already use auth.User.
User = get_user_model()


class Student(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_WARNING = "warning"
    STATUS_OVERDUE = "overdue"
    STATUS_REVIEW = "review"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Enrolled"),
        (STATUS_INACTIVE, "Inactive"),
        (STATUS_WARNING, "Warning"),
        (STATUS_OVERDUE, "Overdue"),
        (STATUS_REVIEW, "Review"),
    ]

    student_code = models.CharField(max_length=32, unique=True)
    first_name = models.CharField(max_length=128)
    last_name = models.CharField(max_length=128)
    email = models.EmailField(blank=True, default="")
    phone_number = models.CharField(max_length=32, blank=True, default="")
    grade_level = models.CharField(max_length=64)
    class_name = models.CharField(max_length=128)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    parent_name = models.CharField(max_length=128, blank=True, default="")
    parent_phone = models.CharField(max_length=32, blank=True, default="")
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "Student"
        verbose_name_plural = "Students"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        return f"{self.full_name} ({self.student_code})"


class GradeMatrix(models.Model):
    """Assessment results matrix used by the spreadsheet results editor."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="grade_matrices")
    subject = models.CharField(max_length=64)
    assessment_type = models.CharField(max_length=64, default="exam")
    academic_year = models.CharField(max_length=32, default="2025")
    term = models.CharField(max_length=32, default="Term 1")
    score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total_score = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    grade = models.CharField(max_length=8, blank=True, default="")
    remarks = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student__last_name", "subject", "term"]
        unique_together = [("student", "subject", "assessment_type", "academic_year", "term")]
        verbose_name = "Grade Matrix"
        verbose_name_plural = "Grade Matrices"

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.subject} ({self.grade})"


class FeeLedger(models.Model):
    """School fee ledger representing individual billing and payment records."""

    STATUS_PARTIAL = "partial"
    STATUS_SETTLED = "settled"
    STATUS_OVERDUE = "overdue"

    STATUS_CHOICES = [
        (STATUS_PARTIAL, "Partial"),
        (STATUS_SETTLED, "Settled"),
        (STATUS_OVERDUE, "Overdue"),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="fee_ledgers")
    invoice_code = models.CharField(max_length=64, unique=True)
    term = models.CharField(max_length=32, default="Term 1")
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PARTIAL)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Fee Ledger"
        verbose_name_plural = "Fee Ledgers"

    def save(self, *args, **kwargs):
        self.balance_amount = self.due_amount - self.paid_amount
        if self.balance_amount <= 0:
            self.payment_status = self.STATUS_SETTLED
        elif self.balance_amount > 0:
            self.payment_status = self.STATUS_PARTIAL
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.student.full_name} - {self.invoice_code}"
