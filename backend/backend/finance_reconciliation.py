from __future__ import annotations

import csv
import io
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from app.models import AcademicYear, BankAccount, BankStatement, BankTransaction, Payment, Term

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _staff_for_user, _token_context


READ_ROLES = {"Admin", "Head Teacher", "Bursar"}
WRITE_ROLES = {"Admin", "Bursar"}


def _role(request) -> str:
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_read(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in READ_ROLES)


def _can_write(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in WRITE_ROLES)


def _current_period():
    year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.order_by("-academic_year", "-id").first()
    term = None
    if year:
        term = Term.objects.filter(academic_year=year, is_current=True).first() or Term.objects.filter(academic_year=year).order_by("term", "id").first()
    return year, term


def _money(value) -> str:
    return f"{Decimal(value or 0):,.0f}"


def _unmatched_payments(year=None, term=None):
    reconciled_payment_ids = BankTransaction.objects.filter(
        reconciled=True,
        reconciled_with__isnull=False,
    ).values_list("reconciled_with_id", flat=True)
    queryset = Payment.objects.exclude(id__in=reconciled_payment_ids).filter(
        bill__student__is_active=True,
    ).select_related(
        "bill__student",
        "bill__academic_class__Class",
        "bill__academic_class__academic_year",
        "bill__academic_class__term",
    )
    if year and term:
        queryset = queryset.filter(
            bill__academic_class__academic_year=year,
            bill__academic_class__term=term,
            payment_date__gte=term.start_date,
            payment_date__lte=term.end_date,
        )
    return queryset.order_by("-payment_date", "-id")


def _transaction_row(row: BankTransaction, unmatched: list[Payment]):
    tx_amount = abs(Decimal(row.amount or 0))
    suggestions = []
    if row.transaction_type == "Credit" and not row.reconciled:
        for payment in unmatched:
            payment_amount = Decimal(payment.amount or 0)
            date_gap = abs((payment.payment_date - row.transaction_date).days)
            reference_match = bool(row.reference and payment.reference_no and row.reference.strip().casefold() == payment.reference_no.strip().casefold())
            amount_match = payment_amount == tx_amount
            if reference_match or (amount_match and date_gap <= 7):
                suggestions.append({
                    "payment_id": payment.pk,
                    "student": payment.bill.student.student_name,
                    "reg_no": payment.bill.student.reg_no or "—",
                    "reference": payment.reference_no,
                    "payment_date": payment.payment_date.isoformat(),
                    "amount": str(payment.amount),
                    "amount_display": _money(payment.amount),
                    "reason": "Reference match" if reference_match else f"Same amount · {date_gap} day{'s' if date_gap != 1 else ''} apart",
                })
                if len(suggestions) >= 5:
                    break
    return {
        "id": row.pk,
        "statement_id": row.bank_statement_id,
        "account": str(row.bank_statement.bank_account),
        "date": row.transaction_date.isoformat(),
        "description": row.description,
        "amount": str(row.amount),
        "amount_display": _money(abs(Decimal(row.amount or 0))),
        "type": row.transaction_type,
        "reference": row.reference or "",
        "reconciled": row.reconciled,
        "payment_id": row.reconciled_with_id,
        "reconciled_at": row.reconciliation_date.isoformat() if row.reconciliation_date else "",
        "notes": row.notes or "",
        "suggestions": suggestions,
    }


def _statement_row(row: BankStatement):
    transactions = row.transactions.all()
    total = transactions.count()
    reconciled = transactions.filter(reconciled=True).count()
    return {
        "id": row.pk,
        "account": str(row.bank_account),
        "account_id": row.bank_account_id,
        "date": row.statement_date.isoformat(),
        "opening_balance": str(row.opening_balance),
        "closing_balance": str(row.closing_balance),
        "transactions": total,
        "reconciled": reconciled,
        "unreconciled": max(total - reconciled, 0),
        "uploaded": row.upload_date.isoformat(),
        "file": row.file.url if row.file else "",
    }


def _payment_row(row: Payment):
    return {
        "id": row.pk,
        "student": row.bill.student.student_name,
        "reg_no": row.bill.student.reg_no or "—",
        "class": str(row.bill.academic_class.Class),
        "date": row.payment_date.isoformat(),
        "amount": str(row.amount),
        "amount_display": _money(row.amount),
        "method": row.payment_method,
        "reference": row.reference_no,
    }


def _parse_decimal(value, label: str):
    try:
        return Decimal(str(value or 0).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"Enter a valid {label}.")


def _read_statement_csv(uploaded_file):
    uploaded_file.seek(0)
    text = uploaded_file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for index, raw in enumerate(reader, start=2):
        date_value = (raw.get("Date") or raw.get("date") or "").strip()
        description = (raw.get("Description") or raw.get("description") or "").strip()
        amount_value = (raw.get("Amount") or raw.get("amount") or "").replace(",", "").strip()
        reference = (raw.get("Reference") or raw.get("reference") or "").strip()
        if not date_value and not amount_value and not description:
            continue
        if not date_value or not amount_value:
            raise ValueError(f"CSV row {index} must include Date and Amount.")
        try:
            amount = Decimal(amount_value)
        except InvalidOperation as exc:
            raise ValueError(f"CSV row {index} has an invalid Amount.") from exc
        rows.append({
            "transaction_date": date_value,
            "description": description or "Bank transaction",
            "amount": amount,
            "transaction_type": "Credit" if amount >= 0 else "Debit",
            "reference": reference,
        })
    if not rows:
        raise ValueError("The CSV contains no bank transactions.")
    return rows


class FinanceReconciliationAPIView(WorkspaceBaseAPIView):
    def _guard(self, request, *, write=False):
        allowed = _can_write(request) if write else _can_read(request)
        if allowed:
            return None
        detail = "Your current role cannot manage bank reconciliation." if write else "Your current role cannot view bank reconciliation."
        return Response({"detail": detail}, status=status.HTTP_403_FORBIDDEN)

    def get(self, request):
        failure = self._guard(request)
        if failure:
            return failure

        year, term = _current_period()
        unmatched_qs = _unmatched_payments(year, term)
        unmatched = list(unmatched_qs[:1000])
        transaction_qs = BankTransaction.objects.select_related(
            "bank_statement__bank_account", "reconciled_with"
        )
        if term:
            transaction_qs = transaction_qs.filter(
                transaction_date__gte=term.start_date,
                transaction_date__lte=term.end_date,
            )
        transaction_qs = transaction_qs.order_by("-transaction_date", "-id")
        unreconciled = list(transaction_qs.filter(reconciled=False)[:1000])
        recent_reconciled = list(transaction_qs.filter(reconciled=True)[:100])
        statements = BankStatement.objects.select_related("bank_account").prefetch_related("transactions").order_by("-statement_date", "-id")[:250]

        unmatched_total = unmatched_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        unreconciled_credit_total = sum(
            (abs(Decimal(row.amount or 0)) for row in unreconciled if row.transaction_type == "Credit"),
            Decimal("0"),
        )
        return Response({
            "period": {
                "year": str(year or ""),
                "term": str(term or ""),
                "start": term.start_date.isoformat() if term else "",
                "end": term.end_date.isoformat() if term else "",
            },
            "permissions": {"write": _can_write(request)},
            "metrics": [
                {"label": "Unreconciled bank credits", "value": len([row for row in unreconciled if row.transaction_type == "Credit"]), "hint": f"UGX {_money(unreconciled_credit_total)} waiting", "tone": "gold"},
                {"label": "Unmatched payments", "value": len(unmatched), "hint": f"UGX {_money(unmatched_total)} recorded", "tone": "violet"},
                {"label": "Statements", "value": len(statements), "hint": "Uploaded bank statements", "tone": "blue"},
                {"label": "Recently reconciled", "value": len(recent_reconciled), "hint": "Latest matched transactions", "tone": "green"},
            ],
            "accounts": [
                {"id": row.pk, "label": str(row), "bank": row.bank_name, "account_number": row.account_number}
                for row in BankAccount.objects.order_by("bank_name", "account_name")
            ],
            "statements": [_statement_row(row) for row in statements],
            "transactions": [_transaction_row(row, unmatched) for row in unreconciled],
            "payments": [_payment_row(row) for row in unmatched],
            "recent_reconciled": [_transaction_row(row, []) for row in recent_reconciled],
        })

    @transaction.atomic
    def post(self, request):
        failure = self._guard(request, write=True)
        if failure:
            return failure

        action = str(request.data.get("action") or "").strip().lower()

        if action == "upload_statement":
            upload = request.FILES.get("statement_file")
            if not upload:
                return Response({"detail": "Choose a CSV bank statement to upload."}, status=status.HTTP_400_BAD_REQUEST)
            if not str(upload.name).lower().endswith(".csv"):
                return Response({"detail": "Bank statement import currently accepts CSV files only."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                account = BankAccount.objects.get(pk=request.data.get("bank_account"))
                statement_date = request.data.get("statement_date")
                if not statement_date:
                    raise ValueError("Choose the statement date.")
                opening = _parse_decimal(request.data.get("opening_balance"), "opening balance")
                closing = _parse_decimal(request.data.get("closing_balance"), "closing balance")
                rows = _read_statement_csv(upload)
            except BankAccount.DoesNotExist:
                return Response({"detail": "Choose a valid bank account."}, status=status.HTTP_400_BAD_REQUEST)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            upload.seek(0)
            statement = BankStatement.objects.create(
                bank_account=account,
                statement_date=statement_date,
                opening_balance=opening,
                closing_balance=closing,
                uploaded_by=_staff_for_user(request.user),
                file=upload,
            )
            try:
                BankTransaction.objects.bulk_create([
                    BankTransaction(bank_statement=statement, **row) for row in rows
                ])
            except Exception as exc:
                transaction.set_rollback(True)
                return Response({"detail": f"The statement could not be imported: {exc}"}, status=status.HTTP_400_BAD_REQUEST)
            return Response({"detail": f"Statement uploaded with {len(rows)} transaction(s).", "id": statement.pk}, status=status.HTTP_201_CREATED)

        if action == "reconcile":
            try:
                bank_transaction = BankTransaction.objects.select_for_update().select_related("bank_statement").get(pk=request.data.get("transaction_id"))
                payment = Payment.objects.select_for_update().select_related("bill__student").get(pk=request.data.get("payment_id"))
            except (BankTransaction.DoesNotExist, Payment.DoesNotExist, ValueError, TypeError):
                return Response({"detail": "Choose a valid bank transaction and payment."}, status=status.HTTP_400_BAD_REQUEST)

            if bank_transaction.reconciled:
                return Response({"detail": "This bank transaction is already reconciled."}, status=status.HTTP_409_CONFLICT)
            if bank_transaction.transaction_type != "Credit":
                return Response({"detail": "Student payments can only be matched to bank credit transactions."}, status=status.HTTP_400_BAD_REQUEST)
            if BankTransaction.objects.filter(reconciled=True, reconciled_with=payment).exists():
                return Response({"detail": "This payment is already reconciled to another bank transaction."}, status=status.HTTP_409_CONFLICT)

            bank_amount = abs(Decimal(bank_transaction.amount or 0))
            payment_amount = Decimal(payment.amount or 0)
            if bank_amount != payment_amount:
                return Response({"detail": f"Amounts do not match: bank UGX {_money(bank_amount)} vs payment UGX {_money(payment_amount)}."}, status=status.HTTP_409_CONFLICT)

            bank_transaction.reconciled = True
            bank_transaction.reconciled_with = payment
            bank_transaction.reconciliation_date = timezone.now()
            bank_transaction.notes = str(request.data.get("notes") or "").strip()[:1000]
            bank_transaction.save(update_fields=["reconciled", "reconciled_with", "reconciliation_date", "notes"])
            return Response({"detail": f"Bank transaction matched to {payment.bill.student.student_name} payment {payment.reference_no}."})

        return Response({"detail": "Unknown bank reconciliation action."}, status=status.HTTP_400_BAD_REQUEST)
