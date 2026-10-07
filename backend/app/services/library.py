from datetime import timedelta
from decimal import Decimal, ROUND_UP

from django.db import transaction
from django.utils import timezone

from app.models import (
    AcademicClass,
    BillItem,
    LibraryAudit,
    LibraryCopy,
    LibraryFine,
    LibraryLoan,
    LibraryPolicy,
    Staff,
    Student,
    StudentBillItem,
)


class CirculationError(ValueError):
    pass


def _fine_ledger_key(fine):
    return f"library-fine:{fine.pk}"


def _post_student_fine_to_ledger(fine):
    """Create or update the matching student fee charge for a library fine."""
    student = fine.loan.student
    if not student:
        return None

    academic_class = AcademicClass.objects.filter(
        academic_year=student.academic_year,
        term=student.term,
        Class=student.current_class,
    ).first()
    if not academic_class:
        return None

    # Reuse the normal billing service so the learner always has one complete
    # bill for the term before the library penalty is attached.
    from app.services.students import create_student_bill

    bill = create_student_bill(student, academic_class)
    bill_item = BillItem.objects.filter(item_name__iexact="Library Fine").order_by("pk").first()
    if not bill_item:
        bill_item = BillItem.objects.create(
            item_name="Library Fine",
            category="One Off",
            bill_duration="None",
            description="Library late, damage and replacement charges",
        )
    reason = fine.get_reason_display()
    book = fine.loan.copy.book.title
    charge, _ = StudentBillItem.objects.update_or_create(
        bill=bill,
        notes=_fine_ledger_key(fine),
        defaults={
            "bill_item": bill_item,
            "description": f"Library {reason.lower()} charge — {book}",
            "amount": fine.amount,
            "fee_category": "Other",
        },
    )
    return charge


@transaction.atomic
def issue_copy(*, copy_id, actor, student_id=None, staff_id=None):
    copy = LibraryCopy.objects.select_for_update().select_related("book").get(pk=copy_id)
    if copy.status != LibraryCopy.STATUS_AVAILABLE:
        raise CirculationError("This copy is not available.")
    if bool(student_id) == bool(staff_id):
        raise CirculationError("Choose exactly one borrower.")
    borrower_type = "student" if student_id else "staff"
    borrower = Student.objects.get(pk=student_id, is_active=True) if student_id else Staff.objects.get(pk=staff_id, staff_status="Active")
    policy, _ = LibraryPolicy.objects.get_or_create(borrower_type=borrower_type)
    borrower_filter = {borrower_type: borrower}
    active = LibraryLoan.objects.filter(returned_at__isnull=True, **borrower_filter)
    if active.count() >= policy.maximum_books:
        raise CirculationError("The borrower has reached the borrowing limit.")
    if policy.block_when_overdue and active.filter(due_at__lt=timezone.now()).exists():
        raise CirculationError("The borrower has an overdue item.")
    fine_borrower_filter = {f"loan__{borrower_type}": borrower}
    if LibraryFine.objects.filter(status=LibraryFine.STATUS_OUTSTANDING, **fine_borrower_filter).exists():
        raise CirculationError("The borrower has an outstanding library fine.")
    issued_at = timezone.now()
    loan = LibraryLoan.objects.create(
        copy=copy, issued_at=issued_at, due_at=issued_at + timedelta(days=policy.loan_days),
        issued_by=actor, **borrower_filter,
    )
    copy.status = LibraryCopy.STATUS_ON_LOAN
    copy.save(update_fields=("status",))
    LibraryAudit.objects.create(loan=loan, copy=copy, action="issued", actor=actor)
    return loan


@transaction.atomic
def _assess_fine(*, loan, reason, amount, actor, notes=""):
    amount = Decimal(amount or 0).quantize(Decimal("0.01"))
    if amount <= 0:
        return None
    fine, _ = LibraryFine.objects.update_or_create(
        loan=loan, reason=reason,
        defaults={"amount": amount, "status": LibraryFine.STATUS_OUTSTANDING, "notes": notes, "assessed_by": actor,
                  "resolved_by": None, "resolved_at": None},
    )
    charge = _post_student_fine_to_ledger(fine)
    LibraryAudit.objects.create(
        loan=loan, copy=loan.copy, action="fine_assessed", actor=actor,
        details={
            "fine_id": fine.pk,
            "reason": reason,
            "amount": str(amount),
            "student_bill_item_id": getattr(charge, "pk", None),
        },
    )
    return fine


@transaction.atomic
def return_loan(*, loan_id, actor, condition="good", damage_amount=0, notes=""):
    if condition not in {"good", "damaged"}:
        raise CirculationError("Invalid return condition.")
    loan = LibraryLoan.objects.select_for_update().select_related("copy").get(pk=loan_id)
    if loan.returned_at:
        return loan
    returned_at = timezone.now()
    loan.returned_at = returned_at
    loan.returned_by = actor
    loan.return_condition = condition
    loan.save(update_fields=("returned_at", "returned_by", "return_condition"))
    loan.copy.status = LibraryCopy.STATUS_DAMAGED if condition == "damaged" else LibraryCopy.STATUS_AVAILABLE
    loan.copy.save(update_fields=("status",))
    borrower_type = "student" if loan.student_id else "staff"
    policy, _ = LibraryPolicy.objects.get_or_create(borrower_type=borrower_type)
    if returned_at > loan.due_at and policy.daily_fine > 0:
        overdue_seconds = Decimal(str((returned_at - loan.due_at).total_seconds()))
        overdue_days = (overdue_seconds / Decimal("86400")).to_integral_value(rounding=ROUND_UP)
        _assess_fine(
            loan=loan, reason=LibraryFine.REASON_OVERDUE, amount=overdue_days * policy.daily_fine,
            actor=actor, notes=f"{overdue_days} overdue day(s).",
        )
    if condition == "damaged":
        _assess_fine(
            loan=loan, reason=LibraryFine.REASON_DAMAGED, amount=damage_amount,
            actor=actor, notes=notes,
        )
    LibraryAudit.objects.create(loan=loan, copy=loan.copy, action="returned", actor=actor, details={"condition": condition})
    return loan


@transaction.atomic
def mark_loan_lost(*, loan_id, actor, amount, notes=""):
    loan = LibraryLoan.objects.select_for_update().select_related("copy").get(pk=loan_id)
    if loan.returned_at:
        raise CirculationError("A closed loan cannot be marked lost.")
    loan.returned_at = timezone.now()
    loan.returned_by = actor
    loan.return_condition = "lost"
    loan.notes = notes
    loan.save(update_fields=("returned_at", "returned_by", "return_condition", "notes"))
    loan.copy.status = LibraryCopy.STATUS_LOST
    loan.copy.save(update_fields=("status",))
    _assess_fine(loan=loan, reason=LibraryFine.REASON_LOST, amount=amount, actor=actor, notes=notes)
    LibraryAudit.objects.create(loan=loan, copy=loan.copy, action="marked_lost", actor=actor, details={"notes": notes})
    return loan


@transaction.atomic
def resolve_fine(*, fine_id, actor, resolution):
    if resolution not in {LibraryFine.STATUS_PAID, LibraryFine.STATUS_WAIVED}:
        raise CirculationError("Invalid fine resolution.")
    fine = LibraryFine.objects.select_for_update().get(pk=fine_id)
    if fine.status != LibraryFine.STATUS_OUTSTANDING:
        return fine
    fine.status = resolution
    fine.resolved_by = actor
    fine.resolved_at = timezone.now()
    fine.save(update_fields=("status", "resolved_by", "resolved_at"))
    if resolution == LibraryFine.STATUS_WAIVED:
        StudentBillItem.objects.filter(notes=_fine_ledger_key(fine)).update(
            amount=Decimal("0.00"),
            description=f"WAIVED — library {fine.get_reason_display().lower()} charge",
        )
    LibraryAudit.objects.create(
        loan=fine.loan, copy=fine.loan.copy, action=f"fine_{resolution}", actor=actor,
        details={"fine_id": fine.pk, "amount": str(fine.amount)},
    )
    return fine


@transaction.atomic
def renew_loan(*, loan_id, actor):
    loan = LibraryLoan.objects.select_for_update().get(pk=loan_id)
    if loan.returned_at:
        raise CirculationError("A returned loan cannot be renewed.")
    borrower_type = "student" if loan.student_id else "staff"
    policy, _ = LibraryPolicy.objects.get_or_create(borrower_type=borrower_type)
    if loan.renewals >= policy.renewal_limit:
        raise CirculationError("The renewal limit has been reached.")
    loan.due_at = max(loan.due_at, timezone.now()) + timedelta(days=policy.loan_days)
    loan.renewals += 1
    loan.save(update_fields=("due_at", "renewals"))
    LibraryAudit.objects.create(loan=loan, copy=loan.copy, action="renewed", actor=actor)
    return loan
