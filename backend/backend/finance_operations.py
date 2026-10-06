from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from app.models import AcademicClass, BankAccount, BankStatement, BankTransaction, ClassBill, ClassRegister, Payment, StudentBill, StudentBillItem

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context


READ_ROLES = {"Admin", "Head Teacher", "Bursar"}
WRITE_ROLES = {"Admin", "Bursar"}


def _role(request) -> str:
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_read(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in READ_ROLES)


def _can_write(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in WRITE_ROLES)


def _money(value) -> str:
    return f"{Decimal(value or 0):,.2f}"


def _reconciliation_payload(request):
    statements = BankStatement.objects.select_related("bank_account", "uploaded_by").order_by("-statement_date", "-id")[:250]
    transactions = BankTransaction.objects.select_related("bank_statement__bank_account", "reconciled_with__bill__student").order_by("-transaction_date", "-id")
    payments = Payment.objects.select_related("bill__student").order_by("-payment_date", "-id")

    reconciled_payment_ids = set(
        BankTransaction.objects.filter(reconciled=True, reconciled_with__isnull=False).values_list("reconciled_with_id", flat=True)
    )
    unmatched_payments = payments.exclude(pk__in=reconciled_payment_ids)[:500]
    unmatched_transactions = transactions.filter(reconciled=False, transaction_type="Credit")[:500]
    matched = transactions.filter(reconciled=True, reconciled_with__isnull=False)[:500]

    return {
        "title": "Bank Reconciliation",
        "description": "Match bank statement credits to recorded school-fee payments without leaving the finance workspace.",
        "can_write": _can_write(request),
        "metrics": {
            "bank_accounts": BankAccount.objects.count(),
            "statements": BankStatement.objects.count(),
            "unmatched_bank": transactions.filter(reconciled=False, transaction_type="Credit").count(),
            "unmatched_payments": payments.exclude(pk__in=reconciled_payment_ids).count(),
            "matched": transactions.filter(reconciled=True, reconciled_with__isnull=False).count(),
        },
        "accounts": [
            {
                "id": row.pk,
                "bank": row.bank_name,
                "account_name": row.account_name,
                "account_number": row.account_number,
                "balance": _money(row.balance),
            }
            for row in BankAccount.objects.order_by("bank_name", "account_name")[:100]
        ],
        "statements": [
            {
                "id": row.pk,
                "account": str(row.bank_account),
                "date": row.statement_date.isoformat(),
                "opening": _money(row.opening_balance),
                "closing": _money(row.closing_balance),
                "transactions": row.transactions.count(),
            }
            for row in statements
        ],
        "unmatched_transactions": [
            {
                "id": row.pk,
                "date": row.transaction_date.isoformat(),
                "account": str(row.bank_statement.bank_account),
                "description": row.description,
                "reference": row.reference or "",
                "amount": _money(row.amount),
            }
            for row in unmatched_transactions
        ],
        "unmatched_payments": [
            {
                "id": row.pk,
                "date": row.payment_date.isoformat(),
                "student": row.bill.student.student_name,
                "student_number": row.bill.student.display_student_id,
                "reference": row.reference_no,
                "method": row.payment_method,
                "amount": _money(row.amount),
            }
            for row in unmatched_payments
        ],
        "matched": [
            {
                "transaction_id": row.pk,
                "payment_id": row.reconciled_with_id,
                "date": row.transaction_date.isoformat(),
                "student": row.reconciled_with.bill.student.student_name if row.reconciled_with_id else "",
                "bank_reference": row.reference or "",
                "payment_reference": row.reconciled_with.reference_no if row.reconciled_with_id else "",
                "amount": _money(row.amount),
            }
            for row in matched
        ],
    }


def _sync_class_billing(academic_class: AcademicClass) -> dict:
    class_bills = list(ClassBill.objects.filter(academic_class=academic_class).select_related("bill_item"))
    register = ClassRegister.objects.filter(
        academic_class_stream__academic_class=academic_class,
        student__is_active=True,
    ).select_related("student").distinct()

    created_bills = 0
    created_items = 0
    updated_items = 0
    students = set()

    for row in register:
        student = row.student
        if student.pk in students:
            continue
        students.add(student.pk)
        bill, created = StudentBill.objects.get_or_create(
            student=student,
            academic_class=academic_class,
            defaults={"status": "Unpaid"},
        )
        created_bills += int(created)
        for class_bill in class_bills:
            item, item_created = StudentBillItem.objects.get_or_create(
                bill=bill,
                bill_item=class_bill.bill_item,
                defaults={
                    "description": class_bill.bill_item.description,
                    "amount": class_bill.amount,
                },
            )
            if item_created:
                created_items += 1
            elif item.amount != class_bill.amount or item.description != class_bill.bill_item.description:
                item.amount = class_bill.amount
                item.description = class_bill.bill_item.description
                item.save(update_fields=["amount", "description"])
                updated_items += 1

    return {
        "students": len(students),
        "templates": len(class_bills),
        "created_bills": created_bills,
        "created_items": created_items,
        "updated_items": updated_items,
    }


class FinanceOperationsAPIView(WorkspaceBaseAPIView):
    def get(self, request, screen: str):
        if not _can_read(request):
            return Response({"detail": "Your current role cannot access finance operations."}, status=status.HTTP_403_FORBIDDEN)
        if screen == "reconciliation":
            return Response(_reconciliation_payload(request))
        if screen == "billing":
            classes = AcademicClass.objects.select_related("Class", "academic_year", "term").order_by(
                "-academic_year__academic_year", "term__term", "Class__name"
            )[:1000]
            return Response({
                "title": "Billing Synchronisation",
                "description": "Repair or initialise student bills from the class billing templates for one academic class.",
                "can_write": _can_write(request),
                "classes": [
                    {
                        "id": row.pk,
                        "label": str(row),
                        "class": str(row.Class),
                        "year": str(row.academic_year),
                        "term": str(row.term),
                        "templates": row.class_bills.count(),
                        "registered": ClassRegister.objects.filter(academic_class_stream__academic_class=row, student__is_active=True).values("student_id").distinct().count(),
                        "billed": StudentBill.objects.filter(academic_class=row, student__is_active=True).count(),
                    }
                    for row in classes
                ],
            })
        return Response({"detail": "Finance workspace not found."}, status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    def post(self, request, screen: str):
        if not _can_write(request):
            return Response({"detail": "Your current role cannot change finance operations."}, status=status.HTTP_403_FORBIDDEN)

        if screen == "reconciliation":
            action = str(request.data.get("action") or "").strip().lower()
            if action == "match":
                transaction_row = BankTransaction.objects.select_for_update().filter(pk=request.data.get("transaction_id")).first()
                payment = Payment.objects.select_for_update().filter(pk=request.data.get("payment_id")).first()
                if not transaction_row or not payment:
                    return Response({"detail": "Choose a valid bank transaction and payment."}, status=status.HTTP_400_BAD_REQUEST)
                if transaction_row.transaction_type != "Credit":
                    return Response({"detail": "Only bank credits can be reconciled to fee payments."}, status=status.HTTP_400_BAD_REQUEST)
                if transaction_row.reconciled:
                    return Response({"detail": "This bank transaction is already reconciled."}, status=status.HTTP_409_CONFLICT)
                if BankTransaction.objects.filter(reconciled=True, reconciled_with=payment).exists():
                    return Response({"detail": "That payment is already reconciled to another bank transaction."}, status=status.HTTP_409_CONFLICT)
                if Decimal(transaction_row.amount) != Decimal(payment.amount):
                    return Response({"detail": "The bank transaction and payment amounts must match exactly."}, status=status.HTTP_409_CONFLICT)
                transaction_row.reconciled = True
                transaction_row.reconciled_with = payment
                transaction_row.reconciliation_date = __import__("django.utils.timezone", fromlist=["now"]).now()
                transaction_row.notes = str(request.data.get("notes") or transaction_row.notes or "")
                transaction_row.save(update_fields=["reconciled", "reconciled_with", "reconciliation_date", "notes"])
                return Response({"detail": "Bank transaction matched to the payment successfully."})

            if action == "unmatch":
                transaction_row = BankTransaction.objects.select_for_update().filter(pk=request.data.get("transaction_id"), reconciled=True).first()
                if not transaction_row:
                    return Response({"detail": "The reconciled bank transaction was not found."}, status=status.HTTP_404_NOT_FOUND)
                transaction_row.reconciled = False
                transaction_row.reconciled_with = None
                transaction_row.reconciliation_date = None
                transaction_row.notes = str(request.data.get("notes") or transaction_row.notes or "")
                transaction_row.save(update_fields=["reconciled", "reconciled_with", "reconciliation_date", "notes"])
                return Response({"detail": "Reconciliation match removed."})

            return Response({"detail": "Unknown reconciliation action."}, status=status.HTTP_400_BAD_REQUEST)

        if screen == "billing":
            academic_class = AcademicClass.objects.select_for_update().filter(pk=request.data.get("academic_class_id")).first()
            if not academic_class:
                return Response({"detail": "Choose a valid academic class."}, status=status.HTTP_400_BAD_REQUEST)
            summary = _sync_class_billing(academic_class)
            return Response({"detail": "Class billing synchronised successfully.", "summary": summary})

        return Response({"detail": "Unknown finance action."}, status=status.HTTP_404_NOT_FOUND)
