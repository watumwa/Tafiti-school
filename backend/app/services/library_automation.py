from decimal import Decimal, ROUND_UP

from django.db import transaction
from django.utils import timezone

from app.models import LibraryFine, LibraryLoan, LibraryPolicy, ParentNotification
from app.services.library import _assess_fine


@transaction.atomic
def accrue_overdue_library_fines(*, actor=None):
    """Accrue the full overdue amount for every open overdue loan.

    The LibraryFine row and matching student-ledger charge are updated in place,
    so running this job repeatedly is idempotent for the same day.
    """
    now = timezone.now()
    policy, _ = LibraryPolicy.objects.get_or_create(borrower_type="student")
    if Decimal(policy.daily_fine or 0) <= 0:
        return {"checked": 0, "updated": 0, "notifications": 0}

    loans = LibraryLoan.objects.select_for_update().select_related(
        "student", "copy__book"
    ).filter(student__isnull=False, returned_at__isnull=True, due_at__lt=now)
    checked = updated = notifications = 0
    for loan in loans:
        checked += 1
        overdue_seconds = Decimal(str((now - loan.due_at).total_seconds()))
        overdue_days = int((overdue_seconds / Decimal("86400")).to_integral_value(rounding=ROUND_UP))
        amount = Decimal(overdue_days) * Decimal(policy.daily_fine)
        previous = LibraryFine.objects.filter(loan=loan, reason=LibraryFine.REASON_OVERDUE).first()
        previous_amount = Decimal(previous.amount) if previous else Decimal("0")
        fine = _assess_fine(
            loan=loan,
            reason=LibraryFine.REASON_OVERDUE,
            amount=amount,
            actor=actor,
            notes=f"{overdue_days} overdue day(s); automatically accrued {now:%Y-%m-%d}.",
        )
        if fine and Decimal(fine.amount) != previous_amount:
            updated += 1
        if loan.student and loan.student.parent_accesses.filter(is_active=True, is_verified=True).exists():
            for access in loan.student.parent_accesses.filter(is_active=True, is_verified=True):
                _notification, created = ParentNotification.objects.get_or_create(
                    user=access.user,
                    source_key=f"library-overdue:{loan.pk}:{now.date().isoformat()}",
                    defaults={
                        "student": loan.student,
                        "kind": "library",
                        "title": "Library book overdue",
                        "message": f"{loan.copy.book.title} is {overdue_days} day(s) overdue. Current fine: UGX {amount:,.0f}.",
                        "destination": "",
                    },
                )
                notifications += int(created)
    return {"checked": checked, "updated": updated, "notifications": notifications}
