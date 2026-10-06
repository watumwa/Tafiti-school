from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from app.models import (
    AcademicClass,
    AcademicYear,
    BankAccount,
    BankStatement,
    BankTransaction,
    BillItem,
    ClassBill,
    ClassRegister,
    Payment,
    Student,
    StudentBill,
    Term,
)
from app.services.fees_carry_forward import build_carry_forward_preview, post_carry_forward
from app.services.students import create_student_bill

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context


READ_ROLES = {"Admin", "Head Teacher", "Bursar"}
WRITE_ROLES = {"Admin", "Bursar"}


def _role(request):
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_read(request):
    return bool(request.user.is_superuser or _role(request) in READ_ROLES)


def _can_write(request):
    return bool(request.user.is_superuser or _role(request) in WRITE_ROLES)


def _money(value):
    return f"{Decimal(value or 0):,.0f}"


def _decimal(value, label):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label} must be a valid amount.")
    if parsed <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return parsed.quantize(Decimal("0.01"))


def _current_period():
    year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.order_by("-academic_year", "-id").first()
    term = None
    if year:
        term = Term.objects.filter(academic_year=year, is_current=True).first() or Term.objects.filter(academic_year=year).order_by("term", "id").first()
    return year, term


def _billing_payload():
    year, term = _current_period()
    classes = AcademicClass.objects.select_related("Class", "academic_year", "term").order_by(
        "-academic_year__academic_year", "term__term", "Class__name"
    )
    if year:
        classes = classes.filter(academic_year=year)
    if term:
        classes = classes.filter(term=term)
    rows = []
    for academic_class in classes[:500]:
        registered = ClassRegister.objects.filter(
            academic_class_stream__academic_class=academic_class,
            student__is_active=True,
        ).values("student_id").distinct().count()
        billed = StudentBill.objects.filter(academic_class=academic_class, student__is_active=True).count()
        templates = ClassBill.objects.filter(academic_class=academic_class).count()
        rows.append({
            "id": academic_class.pk,
            "class": str(academic_class.Class),
            "year": str(academic_class.academic_year),
            "term": str(academic_class.term),
            "students": registered,
            "bills": billed,
            "templates": templates,
        })
    return {
        "period": {"year": str(year or ""), "term": str(term or "")},
        "classes": rows,
        "bill_items": [
            {"id": item.pk, "label": item.item_name, "category": item.category, "description": item.description}
            for item in BillItem.objects.order_by("item_name")[:500]
        ],
    }


def _carry_payload(request):
    _year, current_term = _current_period()
    terms = Term.objects.select_related("academic_year").order_by("-academic_year__academic_year", "term", "id")
    source_id = request.query_params.get("source_term")
    target_id = request.query_params.get("target_term")
    source = Term.objects.select_related("academic_year").filter(pk=source_id).first() if source_id else None
    target = Term.objects.select_related("academic_year").filter(pk=target_id).first() if target_id else current_term
    if not source and target:
        source = Term.objects.select_related("academic_year").filter(end_date__lt=target.start_date).order_by("-end_date", "-id").first()
    rows = []
    preview_total = Decimal("0")
    if source and target and source.pk != target.pk:
        preview = build_carry_forward_preview(
            source_term=source,
            target_term=target,
            class_id=request.query_params.get("class_id") or "",
            active_students_only=(request.query_params.get("active_only", "1") != "0"),
            student_id=request.query_params.get("student_id") or "",
        )
        for row in preview[:2500]:
            if row.can_post:
                preview_total += Decimal(row.outstanding)
            rows.append({
                "student_id": row.student.pk,
                "student": row.student.student_name,
                "student_number": row.student.display_student_id,
                "source_bill_id": row.source_bill.pk,
                "source_class": str(row.source_bill.academic_class),
                "target_class": str(row.target_academic_class or "Not configured"),
                "outstanding": _money(row.outstanding),
                "can_post": row.can_post,
            })
    return {
        "terms": [{"id": item.pk, "label": f"{item.academic_year} · Term {item.term}"} for item in terms[:100]],
        "source_term_id": source.pk if source else None,
        "target_term_id": target.pk if target else None,
        "rows": rows,
        "total": _money(preview_total),
    }


def _reconciliation_payload():
    reconciled_payment_ids = BankTransaction.objects.filter(
        reconciled=True, reconciled_with__isnull=False
    ).values_list("reconciled_with_id", flat=True)
    transactions = BankTransaction.objects.filter(reconciled=False).select_related(
        "bank_statement__bank_account"
    ).order_by("-transaction_date", "-id")[:1000]
    payments = Payment.objects.exclude(id__in=reconciled_payment_ids).select_related(
        "bill__student"
    ).order_by("-payment_date", "-id")[:1500]
    return {
        "bank_accounts": [{"id": row.pk, "label": str(row)} for row in BankAccount.objects.order_by("bank_name", "account_name")],
        "statements": [{
            "id": row.pk,
            "account": str(row.bank_account),
            "date": row.statement_date.isoformat(),
            "opening": _money(row.opening_balance),
            "closing": _money(row.closing_balance),
            "transactions": row.transactions.count(),
        } for row in BankStatement.objects.select_related("bank_account").prefetch_related("transactions").order_by("-statement_date", "-id")[:200]],
        "transactions": [{
            "id": row.pk,
            "date": row.transaction_date.isoformat(),
            "account": str(row.bank_statement.bank_account),
            "description": row.description,
            "amount": _money(abs(row.amount)),
            "type": row.transaction_type,
            "reference": row.reference or "",
        } for row in transactions],
        "payments": [{
            "id": row.pk,
            "date": row.payment_date.isoformat(),
            "student": row.bill.student.student_name,
            "student_number": row.bill.student.display_student_id,
            "amount": _money(row.amount),
            "method": row.payment_method,
            "reference": row.reference_no,
        } for row in payments],
    }


class FinanceOperationsAPIView(WorkspaceBaseAPIView):
    def get(self, request, screen: str):
        if not _can_read(request):
            return Response({"detail": "Your current role cannot access finance operations."}, status=status.HTTP_403_FORBIDDEN)
        if screen == "billing":
            payload = _billing_payload()
        elif screen == "carry-forward":
            payload = _carry_payload(request)
        elif screen == "reconciliation":
            payload = _reconciliation_payload()
        else:
            return Response({"detail": "Finance operation not found."}, status=status.HTTP_404_NOT_FOUND)
        payload["can_write"] = _can_write(request)
        return Response(payload)

    @transaction.atomic
    def post(self, request, screen: str):
        if not _can_write(request):
            return Response({"detail": "Your current role cannot change finance records."}, status=status.HTTP_403_FORBIDDEN)

        if screen == "billing":
            class_ids = request.data.get("class_ids") or []
            if not isinstance(class_ids, list) or not class_ids:
                return Response({"detail": "Choose at least one class."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                normalized_ids = {int(value) for value in class_ids}
            except (TypeError, ValueError):
                return Response({"detail": "One or more selected classes are invalid."}, status=status.HTTP_400_BAD_REQUEST)
            bill_item = BillItem.objects.filter(pk=request.data.get("bill_item_id")).first()
            if not bill_item:
                return Response({"detail": "Choose a valid fee category."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                amount = _decimal(request.data.get("amount"), "Amount")
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            classes = list(AcademicClass.objects.filter(pk__in=normalized_ids).select_related("Class", "academic_year", "term"))
            if len(classes) != len(normalized_ids):
                return Response({"detail": "One or more selected classes are invalid."}, status=status.HTTP_400_BAD_REQUEST)
            generated = 0
            for academic_class in classes:
                ClassBill.objects.update_or_create(
                    academic_class=academic_class,
                    bill_item=bill_item,
                    defaults={"amount": amount},
                )
                student_ids = ClassRegister.objects.filter(
                    academic_class_stream__academic_class=academic_class,
                    student__is_active=True,
                ).values_list("student_id", flat=True).distinct()
                for student in Student.objects.filter(pk__in=student_ids, is_active=True):
                    create_student_bill(student, academic_class)
                    generated += 1
            return Response({
                "detail": f"{bill_item.item_name} was generated for {generated} active student account(s) across {len(classes)} class(es).",
                "generated": generated,
                "classes": len(classes),
            })

        if screen == "carry-forward":
            source = Term.objects.filter(pk=request.data.get("source_term_id")).first()
            target = Term.objects.filter(pk=request.data.get("target_term_id")).first()
            if not source or not target or source.pk == target.pk:
                return Response({"detail": "Choose different valid source and target terms."}, status=status.HTTP_400_BAD_REQUEST)
            if target.start_date <= source.end_date:
                return Response({"detail": "The target term must start after the source term ends."}, status=status.HTTP_400_BAD_REQUEST)
            result = post_carry_forward(
                source_term=source,
                target_term=target,
                class_id=str(request.data.get("class_id") or ""),
                active_students_only=bool(request.data.get("active_students_only", True)),
                student_id=str(request.data.get("student_id") or ""),
            )
            return Response({
                "detail": f"Carried forward UGX {_money(result['posted_total'])} for {result['posted_count']} student account(s).",
                "posted_count": result["posted_count"],
                "skipped_count": result["skipped_count"],
                "posted_total": _money(result["posted_total"]),
            })

        if screen == "reconciliation":
            transaction_row = BankTransaction.objects.select_for_update().filter(pk=request.data.get("transaction_id")).first()
            payment = Payment.objects.select_related("bill__student").filter(pk=request.data.get("payment_id")).first()
            if not transaction_row or not payment:
                return Response({"detail": "Choose a valid bank transaction and payment."}, status=status.HTTP_400_BAD_REQUEST)
            if transaction_row.reconciled:
                return Response({"detail": "This bank transaction is already reconciled."}, status=status.HTTP_409_CONFLICT)
            if BankTransaction.objects.filter(reconciled=True, reconciled_with=payment).exists():
                return Response({"detail": "This payment is already matched to another bank transaction."}, status=status.HTTP_409_CONFLICT)
            if transaction_row.transaction_type != "Credit":
                return Response({"detail": "Only bank credit transactions can be matched to student payments."}, status=status.HTTP_400_BAD_REQUEST)
            if abs(Decimal(transaction_row.amount)) != Decimal(payment.amount):
                return Response({"detail": "Bank transaction and payment amounts must match exactly."}, status=status.HTTP_409_CONFLICT)
            transaction_row.reconciled = True
            transaction_row.reconciled_with = payment
            transaction_row.reconciliation_date = timezone.now()
            transaction_row.save(update_fields=("reconciled", "reconciled_with", "reconciliation_date"))
            return Response({
                "detail": f"Matched {transaction_row.reference or 'bank transaction'} to payment {payment.reference_no} for {payment.bill.student.student_name}."
            })

        return Response({"detail": "Finance action not found."}, status=status.HTTP_404_NOT_FOUND)
