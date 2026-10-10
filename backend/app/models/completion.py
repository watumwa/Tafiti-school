from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class StudentLifecycleEvent(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_TRANSFERRED = "transferred"
    STATUS_LEFT = "left"
    STATUS_GRADUATED = "graduated"
    STATUS_REACTIVATED = "reactivated"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_TRANSFERRED, "Transferred"),
        (STATUS_LEFT, "Left school"),
        (STATUS_GRADUATED, "Graduated"),
        (STATUS_REACTIVATED, "Reactivated"),
    )

    student = models.ForeignKey("app.Student", on_delete=models.CASCADE, related_name="lifecycle_events")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    reason = models.TextField(blank=True)
    from_class = models.ForeignKey("app.Class", null=True, blank=True, on_delete=models.SET_NULL, related_name="student_lifecycle_from")
    to_class = models.ForeignKey("app.Class", null=True, blank=True, on_delete=models.SET_NULL, related_name="student_lifecycle_to")
    from_stream = models.ForeignKey("app.Stream", null=True, blank=True, on_delete=models.SET_NULL, related_name="student_lifecycle_from_stream")
    to_stream = models.ForeignKey("app.Stream", null=True, blank=True, on_delete=models.SET_NULL, related_name="student_lifecycle_to_stream")
    effective_date = models.DateField(default=timezone.localdate)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-effective_date", "-created_at")
        indexes = [models.Index(fields=("student", "status", "effective_date"), name="student_lifecycle_idx")]


class StudentNote(models.Model):
    CATEGORY_GENERAL = "general"
    CATEGORY_DISCIPLINE = "discipline"
    CATEGORY_WELFARE = "welfare"
    CATEGORY_ACADEMIC = "academic"
    CATEGORY_CHOICES = (
        (CATEGORY_GENERAL, "General"),
        (CATEGORY_DISCIPLINE, "Discipline"),
        (CATEGORY_WELFARE, "Welfare"),
        (CATEGORY_ACADEMIC, "Academic"),
    )

    student = models.ForeignKey("app.Student", on_delete=models.CASCADE, related_name="profile_notes")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_GENERAL)
    note = models.TextField()
    is_private = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class StaffContract(models.Model):
    staff = models.ForeignKey("app.Staff", on_delete=models.CASCADE, related_name="contracts")
    contract_type = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    document = models.FileField(upload_to="Staff/Contracts", max_length=500, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "Contract end date cannot be before the start date."})

    class Meta:
        ordering = ("-start_date", "-id")


class StaffLeave(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    staff = models.ForeignKey("app.Staff", on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "Leave end date cannot be before the start date."})

    class Meta:
        ordering = ("-start_date",)


class StaffSalaryHistory(models.Model):
    staff = models.ForeignKey("app.Staff", on_delete=models.CASCADE, related_name="salary_history")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    effective_from = models.DateField()
    reason = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-effective_from", "-id")
        constraints = [models.CheckConstraint(check=models.Q(amount__gte=0), name="staff_salary_history_nonnegative")]


class StaffPerformanceNote(models.Model):
    staff = models.ForeignKey("app.Staff", on_delete=models.CASCADE, related_name="performance_notes")
    title = models.CharField(max_length=150)
    note = models.TextField()
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    review_date = models.DateField(default=timezone.localdate)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.rating is not None and not 1 <= self.rating <= 5:
            raise ValidationError({"rating": "Rating must be between 1 and 5."})

    class Meta:
        ordering = ("-review_date", "-id")


class AdmissionRequirement(models.Model):
    application = models.ForeignKey("app.AdmissionApplication", on_delete=models.CASCADE, related_name="requirements")
    name = models.CharField(max_length=150)
    is_required = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("id",)
        constraints = [models.UniqueConstraint(fields=("application", "name"), name="unique_admission_requirement")]


class PaymentReversal(models.Model):
    payment = models.OneToOneField("app.Payment", on_delete=models.PROTECT, related_name="reversal")
    reason = models.TextField()
    reversed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    reversed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-reversed_at",)


class FeeRefund(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_PAID = "paid"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_PAID, "Paid"),
    )

    payment = models.ForeignKey("app.Payment", on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="requested_fee_refunds")
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_fee_refunds")
    approved_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if Decimal(self.amount or 0) <= 0:
            raise ValidationError({"amount": "Refund amount must be greater than zero."})

    class Meta:
        ordering = ("-requested_at",)


class StudentAccountEntry(models.Model):
    TYPE_OPENING = "opening_balance"
    TYPE_CREDIT_NOTE = "credit_note"
    TYPE_REFUND = "refund"
    TYPE_REVERSAL = "reversal"
    TYPE_CHOICES = (
        (TYPE_OPENING, "Opening balance"),
        (TYPE_CREDIT_NOTE, "Credit note"),
        (TYPE_REFUND, "Refund"),
        (TYPE_REVERSAL, "Payment reversal"),
    )

    student = models.ForeignKey("app.Student", on_delete=models.PROTECT, related_name="account_entries")
    bill = models.ForeignKey("app.StudentBill", null=True, blank=True, on_delete=models.PROTECT, related_name="account_entries")
    entry_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=80, unique=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class ResultPublication(models.Model):
    academic_class = models.OneToOneField("app.AcademicClass", on_delete=models.CASCADE, related_name="result_publication")
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="locked_result_publications")
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="published_result_publications")


class MessageTemplate(models.Model):
    CHANNEL_SMS = "sms"
    CHANNEL_EMAIL = "email"
    CHANNEL_BOTH = "both"
    CHANNEL_CHOICES = ((CHANNEL_SMS, "SMS"), (CHANNEL_EMAIL, "Email"), (CHANNEL_BOTH, "SMS + Email"))

    name = models.CharField(max_length=100, unique=True)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    subject = models.CharField(max_length=180, blank=True)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class OutboundMessage(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_PROCESSING = "processing"
    STATUS_SENT = "sent"
    STATUS_PARTIAL = "partial"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = (
        (STATUS_QUEUED, "Queued"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SENT, "Sent"),
        (STATUS_PARTIAL, "Partially sent"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    channel = models.CharField(max_length=10, choices=MessageTemplate.CHANNEL_CHOICES)
    subject = models.CharField(max_length=180, blank=True)
    body = models.TextField()
    audience_label = models.CharField(max_length=120, blank=True)
    recipient_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)


class OutboundDelivery(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_SENT = "sent"
    STATUS_DELIVERED = "delivered"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = (
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENT, "Sent"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
    )

    message = models.ForeignKey(OutboundMessage, on_delete=models.CASCADE, related_name="deliveries")
    recipient_name = models.CharField(max_length=150, blank=True)
    destination = models.CharField(max_length=254)
    channel = models.CharField(max_length=10, choices=(("sms", "SMS"), ("email", "Email")))
    consented = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    provider_reference = models.CharField(max_length=160, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("message_id", "id")
        indexes = [models.Index(fields=("status", "channel"), name="outbound_delivery_status_idx")]
