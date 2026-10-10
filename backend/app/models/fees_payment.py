from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from app.constants import *


LEDGER_CATEGORY_VALUES = {value for value, _ in LEDGER_CATEGORY_CHOICES}


def normalize_payment_method(value):
    normalized = str(value or "").strip().lower()
    mapping = {
        "cash": "Cash",
        "schoolpay": "SchoolPay",
        "school pay": "SchoolPay",
        "school-pay": "SchoolPay",
        "bank": "Bank",
        "bank transfer": "Bank",
        "cheque": "Other",
        "check": "Other",
        "mobile money": "Mobile Money",
        "mtn mobile money": "Mobile Money",
        "airtel money": "Mobile Money",
        "momo": "Mobile Money",
        "other": "Other",
    }
    return mapping.get(normalized, "Other" if normalized else "")


def infer_ledger_category(*parts):
    text = " ".join(str(part or "") for part in parts).strip().lower()
    if not text:
        return "Other"
    if "transport" in text:
        return "Transport"
    if "uniform" in text:
        return "Uniform"
    if "tuition" in text or "school fee" in text or "school fees" in text or text == "fees":
        return "Tuition"
    return "Other"


class BillItem(models.Model):
    item_name = models.CharField(max_length=50)
    category = models.CharField(max_length=50, choices=BILL_CATEGORY_CHOICES)
    bill_duration = models.CharField(max_length=50, choices=BILL_DURATION_CHOICES)
    description = models.TextField()

    class Meta:
        verbose_name = "billitem"
        verbose_name_plural = "billitems"

    def __str__(self):
        return self.item_name

    def get_absolute_url(self):
        return reverse("billitem_detail", kwargs={"pk": self.pk})


class StudentBill(models.Model):
    student = models.ForeignKey("app.Student", on_delete=models.CASCADE, related_name="bills")
    bill_date = models.DateField(auto_now_add=True)
    academic_class = models.ForeignKey("app.AcademicClass", on_delete=models.CASCADE)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=BILL_STATUS_CHOICES, default="Unpaid")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("student", "academic_class"),
                name="unique_student_bill_per_academic_class",
            )
        ]

    @property
    def total_amount(self):
        return self.items.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    @property
    def approved_adjustments(self):
        if not hasattr(self, "fee_adjustments"):
            return Decimal("0")
        return self.fee_adjustments.filter(status="Approved").aggregate(total=Sum("amount"))["total"] or Decimal("0")

    @property
    def net_amount_due(self):
        return max(Decimal(self.total_amount) - Decimal(self.approved_adjustments), Decimal("0"))

    @property
    def amount_paid(self):
        return self.payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    @property
    def balance(self):
        applied_credits = self.applied_credits.filter(amount__lt=0).aggregate(total=Sum("amount"))["total"] or Decimal("0")
        return Decimal(self.net_amount_due) - Decimal(self.amount_paid) + Decimal(applied_credits)

    @property
    def available_credits(self):
        return self.student.credits.filter(is_applied=False).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    @property
    def payment_status_display(self):
        balance = Decimal(self.balance)
        paid = Decimal(self.amount_paid)
        if balance <= 0 and (Decimal(self.net_amount_due) > 0 or paid > 0):
            return "Paid"
        if paid > 0:
            return "Partial"
        return "Outstanding"

    def apply_credit(self, credit_amount):
        """Apply available student credit oldest-first without duplicating partial credit."""
        requested = Decimal(str(credit_amount or 0))
        if requested <= 0:
            return Decimal("0")

        available = Decimal(self.available_credits)
        if available <= 0:
            return Decimal("0")

        credit_to_apply = min(requested, available, max(Decimal(self.balance), Decimal("0")))
        if credit_to_apply <= 0:
            return Decimal("0")

        credits = self.student.credits.filter(is_applied=False, amount__gt=0).order_by("created_date", "id")
        applied_amount = Decimal("0")

        for credit in credits:
            if applied_amount >= credit_to_apply:
                break

            remaining_needed = credit_to_apply - applied_amount
            credit_amount_available = Decimal(credit.amount)
            amount_from_this_credit = min(remaining_needed, credit_amount_available)
            if amount_from_this_credit <= 0:
                continue

            StudentCredit.objects.create(
                student=self.student,
                amount=-amount_from_this_credit,
                description=f"Applied to bill #{self.id}: {credit.description}",
                is_applied=True,
                applied_date=timezone.now().date(),
                original_bill=credit.original_bill,
                applied_to_bill=self,
            )
            applied_amount += amount_from_this_credit

            remaining_credit = credit_amount_available - amount_from_this_credit
            if remaining_credit <= 0:
                credit.is_applied = True
                credit.applied_date = timezone.now().date()
                credit.applied_to_bill = self
                credit.save(update_fields=["is_applied", "applied_date", "applied_to_bill"])
            else:
                credit.amount = remaining_credit
                credit.save(update_fields=["amount"])

        return applied_amount

    def __str__(self):
        return f"Bill #{self.id} for {self.student}"


class StudentBillItem(models.Model):
    bill = models.ForeignKey(StudentBill, on_delete=models.CASCADE, related_name="items")
    bill_item = models.ForeignKey("app.BillItem", on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    charge_date = models.DateField(null=True, blank=True)
    fee_category = models.CharField(max_length=20, choices=LEDGER_CATEGORY_CHOICES, default="Other")
    notes = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Item {self.description} for Bill #{self.bill.id}"

    def save(self, *args, **kwargs):
        if not self.charge_date and self.bill_id:
            self.charge_date = self.bill.bill_date

        inferred_category = infer_ledger_category(
            getattr(self.bill_item, "category", ""),
            getattr(self.bill_item, "item_name", ""),
            self.description,
        )
        if self.fee_category not in LEDGER_CATEGORY_VALUES or (
            self.fee_category == "Other" and inferred_category != "Other"
        ):
            self.fee_category = inferred_category

        if not self.notes and self.description:
            self.notes = self.description

        super().save(*args, **kwargs)


class ClassBill(models.Model):
    APPLIES_ALL = "All"
    APPLIES_DAY = "Day"
    APPLIES_BOARDING = "Boarding"
    APPLIES_TO_CHOICES = [
        (APPLIES_ALL, "All students"),
        (APPLIES_DAY, "Day students only"),
        (APPLIES_BOARDING, "Boarding students only"),
    ]

    academic_class = models.ForeignKey("app.AcademicClass", on_delete=models.CASCADE, related_name="class_bills")
    bill_item = models.ForeignKey("app.BillItem", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    applies_to = models.CharField(
        max_length=10,
        choices=APPLIES_TO_CHOICES,
        default=APPLIES_ALL,
        help_text="Choose whether this fee applies to all, Day only or Boarding only students.",
    )

    class Meta:
        unique_together = ("academic_class", "bill_item", "applies_to")

    def applies_to_student(self, student):
        return self.applies_to == self.APPLIES_ALL or self.applies_to == getattr(student, "residency_status", self.APPLIES_DAY)


class Payment(models.Model):
    bill = models.ForeignKey(StudentBill, on_delete=models.CASCADE, related_name="payments")
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS)
    fee_category = models.CharField(max_length=20, choices=LEDGER_CATEGORY_CHOICES, blank=True, default="")
    reference_no = models.CharField(max_length=50, unique=True)
    recorded_by = models.CharField(max_length=50)
    notes = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Payment of {self.amount} for Bill #{self.bill.id} on {self.payment_date}"

    def save(self, *args, **kwargs):
        self.payment_method = normalize_payment_method(self.payment_method)

        derived_category = ""
        if not self.fee_category and self.bill_id:
            categories = [
                category
                for category in self.bill.items.values_list("fee_category", flat=True).distinct()
                if category
            ]
            if len(categories) == 1:
                derived_category = categories[0]
            else:
                derived_category = infer_ledger_category(*self.bill.items.values_list("description", flat=True))
            self.fee_category = derived_category
        elif self.fee_category == "Other" and self.bill_id:
            categories = [
                category
                for category in self.bill.items.values_list("fee_category", flat=True).distinct()
                if category and category != "Other"
            ]
            if len(categories) == 1:
                self.fee_category = categories[0]

        super().save(*args, **kwargs)


class StudentCredit(models.Model):
    student = models.ForeignKey("app.Student", on_delete=models.CASCADE, related_name="credits")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    description = models.CharField(max_length=255)
    created_date = models.DateField(auto_now_add=True)
    applied_date = models.DateField(null=True, blank=True)
    is_applied = models.BooleanField(default=False)
    original_bill = models.ForeignKey(StudentBill, on_delete=models.CASCADE, related_name="generated_credits")
    applied_to_bill = models.ForeignKey(StudentBill, on_delete=models.SET_NULL, null=True, blank=True, related_name="applied_credits")

    def __str__(self):
        return f"Credit of {self.amount} for {self.student.student_name}"

    class Meta:
        ordering = ["-created_date"]


class StudentFeeAdjustment(models.Model):
    TYPE_BURSARY = "Bursary"
    TYPE_SCHOLARSHIP = "Scholarship"
    TYPE_STAFF_CHILD = "Staff Child Discount"
    TYPE_SIBLING = "Sibling Discount"
    TYPE_WAIVER = "Waiver"
    TYPE_SPONSOR = "Sponsor"
    TYPE_OTHER = "Other"
    ADJUSTMENT_TYPES = [
        (TYPE_BURSARY, TYPE_BURSARY),
        (TYPE_SCHOLARSHIP, TYPE_SCHOLARSHIP),
        (TYPE_STAFF_CHILD, TYPE_STAFF_CHILD),
        (TYPE_SIBLING, TYPE_SIBLING),
        (TYPE_WAIVER, TYPE_WAIVER),
        (TYPE_SPONSOR, TYPE_SPONSOR),
        (TYPE_OTHER, TYPE_OTHER),
    ]

    CALC_FIXED = "Fixed"
    CALC_PERCENT = "Percentage"
    CALCULATION_TYPES = [(CALC_FIXED, "Fixed amount"), (CALC_PERCENT, "Percentage")]

    STATUS_APPROVED = "Approved"
    STATUS_CANCELLED = "Cancelled"
    STATUS_CHOICES = [(STATUS_APPROVED, "Approved"), (STATUS_CANCELLED, "Cancelled")]

    bill = models.ForeignKey(StudentBill, on_delete=models.CASCADE, related_name="fee_adjustments")
    adjustment_type = models.CharField(max_length=40, choices=ADJUSTMENT_TYPES, default=TYPE_BURSARY)
    calculation_type = models.CharField(max_length=12, choices=CALCULATION_TYPES, default=CALC_FIXED)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reason = models.TextField(blank=True, default="")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_APPROVED)
    created_by = models.CharField(max_length=150, blank=True, default="")
    approved_by = models.CharField(max_length=150, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def clean(self):
        value = Decimal(self.value or 0)
        if value <= 0:
            raise ValidationError({"value": "Adjustment value must be greater than zero."})
        if self.calculation_type == self.CALC_PERCENT and value > 100:
            raise ValidationError({"value": "Percentage adjustments cannot exceed 100%."})

    def calculated_amount(self):
        value = Decimal(self.value or 0)
        gross = Decimal(self.bill.total_amount if self.bill_id else 0)
        if self.calculation_type == self.CALC_PERCENT:
            return (gross * value / Decimal("100")).quantize(Decimal("0.01"))
        return value.quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["amount"])
        self.amount = min(self.calculated_amount(), Decimal(self.bill.total_amount if self.bill_id else 0))
        if self.status == self.STATUS_APPROVED:
            if not self.approved_by:
                self.approved_by = self.created_by
            if not self.approved_at:
                self.approved_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.adjustment_type} - {self.amount} for bill #{self.bill_id}"