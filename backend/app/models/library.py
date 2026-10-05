"""Library catalogue, physical-copy and circulation models."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class LibraryCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class LibraryBook(models.Model):
    title = models.CharField(max_length=255)
    isbn = models.CharField(max_length=30, blank=True, db_index=True)
    author = models.CharField(max_length=150, blank=True)
    publisher = models.CharField(max_length=150, blank=True)
    edition = models.CharField(max_length=50, blank=True)
    publication_year = models.PositiveSmallIntegerField(null=True, blank=True)
    category = models.ForeignKey(LibraryCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="books")
    shelf_location = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("title",)

    def __str__(self):
        return self.title


class LibraryCopy(models.Model):
    STATUS_AVAILABLE = "available"
    STATUS_ON_LOAN = "on_loan"
    STATUS_RESERVED = "reserved"
    STATUS_LOST = "lost"
    STATUS_DAMAGED = "damaged"
    STATUS_REPAIR = "repair"
    STATUS_WITHDRAWN = "withdrawn"
    STATUS_CHOICES = (
        (STATUS_AVAILABLE, "Available"), (STATUS_ON_LOAN, "On loan"),
        (STATUS_RESERVED, "Reserved"), (STATUS_LOST, "Lost"),
        (STATUS_DAMAGED, "Damaged"), (STATUS_REPAIR, "Under repair"),
        (STATUS_WITHDRAWN, "Withdrawn"),
    )
    book = models.ForeignKey(LibraryBook, on_delete=models.PROTECT, related_name="copies")
    accession_number = models.CharField(max_length=40, unique=True)
    barcode = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)
    condition_notes = models.CharField(max_length=255, blank=True)
    acquisition_date = models.DateField(null=True, blank=True)
    acquisition_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ("accession_number",)

    def __str__(self):
        return f"{self.accession_number} - {self.book}"


class LibraryPolicy(models.Model):
    borrower_type = models.CharField(max_length=20, choices=(("student", "Student"), ("staff", "Staff")), unique=True)
    maximum_books = models.PositiveSmallIntegerField(default=3)
    loan_days = models.PositiveSmallIntegerField(default=14)
    renewal_limit = models.PositiveSmallIntegerField(default=1)
    daily_fine = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    block_when_overdue = models.BooleanField(default=True)

    def __str__(self):
        return self.get_borrower_type_display()


class LibraryLoan(models.Model):
    copy = models.ForeignKey(LibraryCopy, on_delete=models.PROTECT, related_name="loans")
    student = models.ForeignKey("app.Student", null=True, blank=True, on_delete=models.PROTECT, related_name="library_loans")
    staff = models.ForeignKey("app.Staff", null=True, blank=True, on_delete=models.PROTECT, related_name="library_loans")
    issued_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField()
    returned_at = models.DateTimeField(null=True, blank=True)
    renewals = models.PositiveSmallIntegerField(default=0)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="issued_library_loans")
    returned_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="returned_library_loans")
    return_condition = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-issued_at",)
        constraints = [
            models.CheckConstraint(
                check=(models.Q(student__isnull=False, staff__isnull=True) | models.Q(student__isnull=True, staff__isnull=False)),
                name="library_loan_exactly_one_borrower",
            ),
            models.UniqueConstraint(fields=("copy",), condition=models.Q(returned_at__isnull=True), name="unique_active_library_copy_loan"),
        ]
        indexes = [models.Index(fields=("due_at", "returned_at"), name="library_loan_due_return_idx")]

    @property
    def is_overdue(self):
        return self.returned_at is None and self.due_at < timezone.now()

    @property
    def borrower(self):
        return self.student or self.staff

    def clean(self):
        if bool(self.student_id) == bool(self.staff_id):
            raise ValidationError("Select exactly one borrower: student or staff.")

    def __str__(self):
        return f"{self.copy} -> {self.borrower}"


class LibraryAudit(models.Model):
    loan = models.ForeignKey(LibraryLoan, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_entries")
    copy = models.ForeignKey(LibraryCopy, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=40)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class LibraryFine(models.Model):
    """A library-managed penalty; it never posts silently into student fees."""

    REASON_OVERDUE = "overdue"
    REASON_LOST = "lost"
    REASON_DAMAGED = "damaged"
    REASON_CHOICES = (
        (REASON_OVERDUE, "Overdue"),
        (REASON_LOST, "Lost item"),
        (REASON_DAMAGED, "Damaged item"),
    )
    STATUS_OUTSTANDING = "outstanding"
    STATUS_PAID = "paid"
    STATUS_WAIVED = "waived"
    STATUS_CHOICES = (
        (STATUS_OUTSTANDING, "Outstanding"),
        (STATUS_PAID, "Paid"),
        (STATUS_WAIVED, "Waived"),
    )

    loan = models.ForeignKey(LibraryLoan, on_delete=models.PROTECT, related_name="fines")
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OUTSTANDING)
    notes = models.TextField(blank=True)
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="assessed_library_fines"
    )
    assessed_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="resolved_library_fines",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-assessed_at",)
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gte=0), name="library_fine_non_negative"),
            models.UniqueConstraint(fields=("loan", "reason"), name="unique_library_fine_reason_per_loan"),
        ]

    def __str__(self):
        return f"{self.get_reason_display()} fine for loan {self.loan_id}"
