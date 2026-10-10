from decimal import Decimal

from django.db.models import Sum
from rest_framework import status
from rest_framework.response import Response

from app.models import BankStatement, Expenditure, Payment, StudentBill, Transaction

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context
from .reports_workspace import _finance as legacy_finance_report


FINANCE_ROLES = {"Admin", "Head Teacher", "Bursar"}


def _role(request):
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _money(value):
    return f"{Decimal(value or 0):.2f}"


def financial_statement_rows():
    """Build a cash statement without double-counting mirrored transactions.

    Payments and Expenditures are mirrored into Transaction by signals. The
    Transaction ledger is therefore the authoritative cash total; operational
    models are shown as components/reconciliation checks rather than added a
    second time.
    """
    fee_collections = Decimal(Payment.objects.aggregate(total=Sum("amount"))["total"] or 0)
    transaction_income = Decimal(
        Transaction.objects.filter(transaction_type="Income").aggregate(total=Sum("amount"))["total"] or 0
    )
    transaction_expense = Decimal(
        Transaction.objects.filter(transaction_type="Expense").aggregate(total=Sum("amount"))["total"] or 0
    )

    budget_linked_expenditure = Decimal("0")
    for expenditure in Expenditure.objects.prefetch_related("items"):
        budget_linked_expenditure += Decimal(expenditure.amount or 0)

    other_income = max(transaction_income - fee_collections, Decimal("0"))
    other_expense = max(transaction_expense - budget_linked_expenditure, Decimal("0"))

    billed = Decimal("0")
    receivables = Decimal("0")
    credits = Decimal("0")
    for bill in StudentBill.objects.prefetch_related(
        "items", "payments", "fee_adjustments", "applied_credits"
    ):
        billed += Decimal(bill.net_amount_due or 0)
        balance = Decimal(bill.balance or 0)
        if balance > 0:
            receivables += balance
        elif balance < 0:
            credits += abs(balance)

    net_movement = transaction_income - transaction_expense
    return [
        {"section": "Income", "item": "School fee collections", "amount": _money(fee_collections)},
        {"section": "Income", "item": "Other recorded income", "amount": _money(other_income)},
        {"section": "Income", "item": "Total cash income", "amount": _money(transaction_income)},
        {"section": "Expenses", "item": "Budget-linked expenditure", "amount": _money(budget_linked_expenditure)},
        {"section": "Expenses", "item": "Other expense transactions", "amount": _money(other_expense)},
        {"section": "Expenses", "item": "Total expenses", "amount": _money(transaction_expense)},
        {"section": "Position", "item": "Net cash movement", "amount": _money(net_movement)},
        {"section": "Position", "item": "Net fees billed after adjustments", "amount": _money(billed)},
        {"section": "Position", "item": "Outstanding fee receivables", "amount": _money(receivables)},
        {"section": "Position", "item": "Student credit balances", "amount": _money(credits)},
    ]


def reconciliation_rows():
    rows = []
    for statement in BankStatement.objects.select_related("bank_account").prefetch_related(
        "transactions"
    ).order_by("-statement_date", "-id"):
        transactions = list(statement.transactions.all())
        credits = sum(
            (Decimal(row.amount or 0) for row in transactions if row.transaction_type == "Credit"),
            Decimal("0"),
        )
        debits = sum(
            (Decimal(row.amount or 0) for row in transactions if row.transaction_type == "Debit"),
            Decimal("0"),
        )
        reconciled = [row for row in transactions if row.reconciled]
        expected_closing = Decimal(statement.opening_balance or 0) + credits - debits
        closing_variance = Decimal(statement.closing_balance or 0) - expected_closing
        rows.append({
            "statement": str(statement),
            "account": str(statement.bank_account),
            "date": statement.statement_date.isoformat(),
            "opening": _money(statement.opening_balance),
            "credits": _money(credits),
            "debits": _money(debits),
            "expected_closing": _money(expected_closing),
            "statement_closing": _money(statement.closing_balance),
            "variance": _money(closing_variance),
            "transactions": len(transactions),
            "reconciled": len(reconciled),
            "unreconciled": len(transactions) - len(reconciled),
        })
    return rows


class FinanceReportsAPIView(WorkspaceBaseAPIView):
    def get(self, request):
        if not request.user.is_superuser and _role(request) not in FINANCE_ROLES:
            return Response(
                {"detail": "Your current role cannot access finance reports."},
                status=status.HTTP_403_FORBIDDEN,
            )

        report = str(request.query_params.get("report") or "summary").strip().lower()
        if report in {"financial-statement", "statement", "income-expense"}:
            rows = financial_statement_rows()
            payload = {"category": "Finance", "report": report, "rows": rows, "count": len(rows)}
        elif report in {"reconciliation", "bank-reconciliation"}:
            rows = reconciliation_rows()
            payload = {"category": "Finance", "report": report, "rows": rows, "count": len(rows)}
        else:
            payload = legacy_finance_report(report)

        from django.utils import timezone
        payload["generated_at"] = timezone.now().isoformat()
        payload["role"] = _role(request)
        return Response(payload)
