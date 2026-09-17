from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone


@dataclass(frozen=True)
class BillStatus:
    label: str
    balance: Decimal
    balance_label: str
    css_class: str


def get_bill_status(bill, *, today=None):
    """Return the single presentation status used across fees screens."""
    today = today or timezone.localdate()
    total = Decimal(str(bill.total_amount or 0))
    paid = Decimal(str(bill.amount_paid or 0))
    raw_balance = Decimal(str(bill.balance or 0))

    if total == 0 and paid == 0 and raw_balance == 0:
        return BillStatus("No Bill", Decimal("0"), "", "secondary")
    if raw_balance < 0:
        return BillStatus("Overpaid", abs(raw_balance), "CR", "info")
    if raw_balance == 0:
        return BillStatus("Paid", Decimal("0"), "", "success")
    if bill.due_date and today > bill.due_date:
        return BillStatus("Overdue", raw_balance, "DR", "danger")
    if paid > 0 or raw_balance < total:
        return BillStatus("Partial", raw_balance, "DR", "warning")
    return BillStatus("Unpaid", raw_balance, "DR", "warning")
