from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from app.models import (
    AcademicYear,
    BankAccount,
    BankStatement,
    BankTransaction,
    Expenditure,
    Payment,
    Term,
)

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context


READ_ROLES = {"Admin", "Head Teacher", "Bursar"}
WRITE_ROLES = {"Admin", "Bursar"}
APPROVAL_ROLES = {"Admin", "Head Teacher"}


def _role(request):
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_read(request):
    return bool(request.user.is_superuser or _role(request) in READ_ROLES)


def _can_write(request):
    return bool(request.user.is_superuser or _role(request) in WRITE_ROLES)


def _can_approve(request):
    return bool(request.user.is_superuser or _role(request) in APPROVAL_ROLES)


def _money(value):
    return f"{Decimal(value or 0):,.2f}"


def _current_period():
    year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.order_by("-academic_year", "-id").first()
    term = None
    if year:
        term = Term.objects.filter(academic_year=year, is_current=True).first() or Term.objects.filter(academic_year=year).order_by("term", "id").first()
    return year, term


def _reconciliation_payload(request):
    year, term = _current_period()
    transactions = BankTransaction.objects.select_related(
        "bank_statement__bank_account", "reconciled_with__bill__student"
    ).order_by("-transaction_date", "-id")
    payments = Payment.objects.select_related("bill__student", "bill__academic_class").order_by("-payment_date", "-id")
    if term:
        transactions = transactions.filter(transaction_date__range=(term.start_date, term.end_date))
        payments = payments.filter(
            bill__academic_class__term=term,
            payment_date__range=(term.start_date, term.end_date),
        )
    used_payment_ids = set(transactions.filter(reconciled=True, reconciled_with__isnull=False).values_list("reconciled_with_id", flat=True))
    unmatched_payments = payments.exclude(pk__in=used_payment_ids)[:1200]
    unreconciled = transactions.filter(reconciled=False)[:1200]
    reconciled = transactions.filter(reconciled=True)[:500]

    return {
        "title": "Bank Reconciliation",
        "description": "Match bank credits to recorded fee receipts without leaving the finance workspace.",
        "period": {"year": str(year or ""), "term": str(term or "")},
        "metrics": {
            "bank_accounts": BankAccount.objects.count(),
            "statements": BankStatement.objects.count(),
            "unreconciled": transactions.filter(reconciled=False).count(),
            "unmatched_payments": payments.exclude(pk__in=used_payment_ids).count(),
        },
        "transactions": [
            {
                "id": row.pk,
                "date": row.transaction_date.isoformat(),
                "bank": str(row.bank_statement.bank_account),
                "description": row.description,
                "amount": _money(row.amount),
                "type": row.transaction_type,
                "reference": row.reference or "",
                "status": "Reconciled" if row.reconciled else "Unreconciled",
                "payment_id": row.reconciled_with_id,
                "payment_reference": row.reconciled_with.reference_no if row.reconciled_with else "",
            }
            for row in list(unreconciled) + list(reconciled)
        ],
        "payments": [
            {
                "id": row.pk,
                "date": row.payment_date.isoformat(),
                "student": row.bill.student.student_name,
                "student_number": row.bill.student.display_student_id,
                "amount": _money(row.amount),
                "method": row.payment_method,
                "reference": row.reference_no,
            }
            for row in unmatched_payments
        ],
        "can_reconcile": _can_write(request),
    }


def _approval_payload(request):
    expenditures = Expenditure.objects.select_related(
        "vendor", "budget_item__department", "budget_item__expense"
    ).order_by("-date_incurred", "-id")[:1500]
    rows = []
    for row in expenditures:
        rows.append({
            "id": row.pk,
            "date": row.date_incurred.isoformat(),
            "description": row.description,
            "vendor": str(row.vendor or "—"),
            "department": str(row.budget_item.department) if row.budget_item_id else "—",
            "expense": str(row.budget_item.expense) if row.budget_item_id else "—",
            "amount": _money(row.amount),
            "payment_status": row.payment_status,
            "approval": "Approved" if row.approved_by else "Pending",
            "approved_by": row.approved_by or "",
        })
    pending = [row for row in rows if row["approval"] == "Pending"]
    return {
        "title": "Finance Approvals",
        "description": "Review expenditure approvals from one queue instead of opening expenditure records one by one.",
        "metrics": {
            "pending": len(pending),
            "approved": len(rows) - len(pending),
            "total_pending": _money(sum((Decimal(row["amount"].replace(",", "")) for row in pending), Decimal("0"))),
        },
        "rows": rows,
        "can_approve": _can_approve(request),
    }


class FinanceOperationsAPIView(WorkspaceBaseAPIView):
    def get(self, request, screen: str):
        if not _can_read(request):
            return Response({"detail": "Your current role cannot access finance operations."}, status=status.HTTP_403_FORBIDDEN)
        if screen == "reconciliation":
            return Response(_reconciliation_payload(request))
        if screen == "approvals":
            return Response(_approval_payload(request))
        return Response({"detail": "Finance operations screen not found."}, status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    def post(self, request, screen: str):
        if screen == "reconciliation":
            if not _can_write(request):
                return Response({"detail": "Your current role cannot reconcile bank transactions."}, status=status.HTTP_403_FORBIDDEN)
            transaction_id = request.data.get("transaction_id")
            payment_id = request.data.get("payment_id")
            try:
                bank_tx = BankTransaction.objects.select_for_update().get(pk=transaction_id)
                payment = Payment.objects.select_for_update().get(pk=payment_id)
            except (BankTransaction.DoesNotExist, Payment.DoesNotExist, TypeError, ValueError):
                return Response({"detail": "Choose a valid bank transaction and payment."}, status=status.HTTP_400_BAD_REQUEST)
            if bank_tx.reconciled:
                return Response({"detail": "This bank transaction is already reconciled."}, status=status.HTTP_409_CONFLICT)
            if BankTransaction.objects.filter(reconciled=True, reconciled_with=payment).exists():
                return Response({"detail": "That payment has already been reconciled."}, status=status.HTTP_409_CONFLICT)
            if bank_tx.transaction_type != "Credit":
                return Response({"detail": "Only bank credit transactions can be matched to fee payments."}, status=status.HTTP_400_BAD_REQUEST)
            if Decimal(bank_tx.amount).copy_abs() != Decimal(payment.amount).copy_abs():
                return Response({"detail": "The bank amount must equal the recorded payment amount before reconciliation."}, status=status.HTTP_400_BAD_REQUEST)
            bank_tx.reconciled = True
            bank_tx.reconciled_with = payment
            bank_tx.reconciliation_date = timezone.now()
            bank_tx.notes = str(request.data.get("notes") or "")[:1000]
            bank_tx.save(update_fields=["reconciled", "reconciled_with", "reconciliation_date", "notes"])
            return Response({"detail": f"Bank transaction matched to receipt {payment.reference_no}."})

        if screen == "approvals":
            if not _can_approve(request):
                return Response({"detail": "Only an administrator or Head Teacher can approve expenditures."}, status=status.HTTP_403_FORBIDDEN)
            action = str(request.data.get("action") or "approve").strip().lower()
            try:
                expenditure = Expenditure.objects.select_for_update().get(pk=request.data.get("expenditure_id"))
            except (Expenditure.DoesNotExist, TypeError, ValueError):
                return Response({"detail": "Choose a valid expenditure."}, status=status.HTTP_400_BAD_REQUEST)
            if action == "approve":
                expenditure.approved_by = request.user.get_full_name() or request.user.get_username()
                expenditure.save(update_fields=["approved_by"])
                return Response({"detail": "Expenditure approved."})
            if action == "revoke":
                expenditure.approved_by = None
                expenditure.save(update_fields=["approved_by"])
                return Response({"detail": "Expenditure approval revoked."})
            return Response({"detail": "Unknown approval action."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Finance operation not found."}, status=status.HTTP_404_NOT_FOUND)
