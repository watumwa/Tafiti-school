from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from app.models import (
    AcademicYear,
    Payment,
    SchoolSetting,
    StudentBill,
    StudentCredit,
    StudentFeeAdjustment,
    Term,
)

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context, record_finance_access_denial


READ_ROLES = {"Admin", "Head Teacher", "Bursar"}
WRITE_ROLES = {"Admin", "Bursar"}
ADJUSTMENT_TYPES = {value for value, _ in StudentFeeAdjustment.ADJUSTMENT_TYPES}
CALCULATION_TYPES = {value for value, _ in StudentFeeAdjustment.CALCULATION_TYPES}


def _role(request) -> str:
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_read(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in READ_ROLES)


def _can_write(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in WRITE_ROLES)


def _money(value) -> str:
    try:
        return f"{Decimal(value or 0):.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return "0.00"


def _decimal(value, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} must be a valid number.")
    if parsed <= 0:
        raise ValueError(f"{field} must be greater than zero.")
    return parsed.quantize(Decimal("0.01"))


def _current_period():
    year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.order_by("-academic_year", "-id").first()
    term = None
    if year:
        term = Term.objects.filter(academic_year=year, is_current=True).first() or Term.objects.filter(academic_year=year).order_by("term", "id").first()
    return year, term


def _status_for_bill(bill: StudentBill) -> str:
    return bill.payment_status_display


def _school_receipt_context() -> dict:
    school = SchoolSetting.objects.first()
    if not school:
        return {"name": "Tafiti School", "motto": "", "address": "", "phone": "", "email": ""}

    def clean(value):
        text = str(value or "").strip()
        return "" if text.lower() in {"none", "null", "-"} else text

    address = ", ".join(part for part in [clean(school.address), clean(school.city)] if part)
    return {
        "name": clean(school.school_name) or "Tafiti School",
        "motto": clean(school.school_motto),
        "address": address,
        "phone": clean(school.mobile) or clean(school.office_phone_number1),
        "email": clean(school.email),
    }


def _reconcile_overpayment_credit(bill: StudentBill) -> Decimal:
    """Keep only the genuinely unused portion of this bill's overpayment as student credit."""
    bill.refresh_from_db()
    applied_to_bill = bill.applied_credits.filter(amount__lt=0).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    credit_reduction = abs(Decimal(applied_to_bill))
    cash_due = max(Decimal(bill.net_amount_due) - credit_reduction, Decimal("0"))
    total_overpayment = max(Decimal(bill.amount_paid) - cash_due, Decimal("0"))

    used_from_this_overpayment = StudentCredit.objects.filter(
        student=bill.student,
        original_bill=bill,
        amount__lt=0,
        is_applied=True,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    remaining_overpayment = max(total_overpayment - abs(Decimal(used_from_this_overpayment)), Decimal("0"))

    unused = StudentCredit.objects.filter(
        student=bill.student,
        original_bill=bill,
        amount__gt=0,
        description__icontains="overpayment credit",
        is_applied=False,
    ).order_by("id")
    first = unused.first()
    if remaining_overpayment > 0:
        if first:
            first.amount = remaining_overpayment
            first.description = f"Overpayment credit from bill #{bill.id}"
            first.save(update_fields=["amount", "description"])
            unused.exclude(pk=first.pk).delete()
        else:
            StudentCredit.objects.create(
                student=bill.student,
                amount=remaining_overpayment,
                description=f"Overpayment credit from bill #{bill.id}",
                original_bill=bill,
                is_applied=False,
            )
    else:
        unused.delete()
    return remaining_overpayment


def _serialize_bill_row(bill: StudentBill) -> dict:
    adjustment = Decimal(bill.approved_adjustments)
    net_due = Decimal(bill.net_amount_due)
    paid = Decimal(bill.amount_paid)
    balance = Decimal(bill.balance)
    available_credit = Decimal(bill.available_credits)
    return {
        "bill_id": bill.pk,
        "student_id": bill.student.pk,
        "student_number": bill.student.display_student_id,
        "student": bill.student.student_name,
        "photo": bill.student.photo.url if getattr(bill.student, "photo", None) else "",
        "class": str(bill.academic_class.Class),
        "stream": str(getattr(bill.student, "stream", "") or ""),
        "year": str(bill.academic_class.academic_year),
        "term": str(bill.academic_class.term),
        "gross_billed": _money(bill.total_amount),
        "adjustments": _money(adjustment),
        "net_due": _money(net_due),
        "paid": _money(paid),
        "balance": _money(max(balance, Decimal("0"))),
        "credit": _money(available_credit),
        "status": _status_for_bill(bill),
        "due_date": bill.due_date.isoformat() if bill.due_date else "",
    }


def _serialize_account(bill: StudentBill, request) -> dict:
    bill.refresh_from_db()
    payments = bill.payments.order_by("-payment_date", "-id")
    adjustments = bill.fee_adjustments.order_by("-created_at", "-id")
    credits = bill.student.credits.select_related("original_bill", "applied_to_bill").order_by("-created_date", "-id")
    return {
        "bill": _serialize_bill_row(bill),
        "student": {
            "id": bill.student.pk,
            "student_number": bill.student.display_student_id,
            "name": bill.student.student_name,
            "photo": bill.student.photo.url if getattr(bill.student, "photo", None) else "",
            "guardian": bill.student.guardian,
            "contact": bill.student.contact,
            "class": str(bill.student.current_class or ""),
            "stream": str(bill.student.stream or ""),
        },
        "items": [
            {
                "id": item.pk,
                "description": item.description,
                "category": item.fee_category,
                "amount": _money(item.amount),
                "date": item.charge_date.isoformat() if item.charge_date else bill.bill_date.isoformat(),
                "notes": item.notes,
            }
            for item in bill.items.select_related("bill_item").order_by("id")
        ],
        "payments": [
            {
                "id": payment.pk,
                "date": payment.payment_date.isoformat(),
                "amount": _money(payment.amount),
                "method": payment.payment_method,
                "category": payment.fee_category,
                "reference": payment.reference_no,
                "recorded_by": payment.recorded_by,
                "notes": payment.notes,
            }
            for payment in payments
        ],
        "adjustments": [
            {
                "id": adjustment.pk,
                "type": adjustment.adjustment_type,
                "calculation_type": adjustment.calculation_type,
                "value": _money(adjustment.value),
                "amount": _money(adjustment.amount),
                "reason": adjustment.reason,
                "status": adjustment.status,
                "created_by": adjustment.created_by,
                "approved_by": adjustment.approved_by,
                "created_at": adjustment.created_at.isoformat(),
            }
            for adjustment in adjustments
        ],
        "credits": [
            {
                "id": credit.pk,
                "date": credit.created_date.isoformat(),
                "amount": _money(credit.amount),
                "description": credit.description,
                "status": "Applied" if credit.is_applied else "Available",
                "applied_date": credit.applied_date.isoformat() if credit.applied_date else "",
                "original_bill_id": credit.original_bill_id,
                "applied_to_bill_id": credit.applied_to_bill_id,
            }
            for credit in credits
        ],
        "available_credit": _money(bill.available_credits),
        "actions": {
            "can_record_payment": _can_write(request),
            "can_add_adjustment": _can_write(request),
            "can_apply_credit": _can_write(request),
            "can_cancel_adjustment": _can_write(request),
        },
        "payment_methods": [choice[0] for choice in Payment._meta.get_field("payment_method").choices],
        "fee_categories": [choice[0] for choice in Payment._meta.get_field("fee_category").choices],
        "adjustment_types": [choice[0] for choice in StudentFeeAdjustment.ADJUSTMENT_TYPES],
    }


def _list_accounts(request):
    current_year, current_term = _current_period()
    year_id = request.query_params.get("year")
    term_id = request.query_params.get("term")
    status_filter = (request.query_params.get("status") or "all").lower()
    q = (request.query_params.get("q") or "").strip()

    queryset = StudentBill.objects.select_related(
        "student", "student__current_class", "student__stream",
        "academic_class__Class", "academic_class__academic_year", "academic_class__term",
    ).prefetch_related("items", "payments", "applied_credits", "fee_adjustments", "student__credits").order_by(
        "student__student_name", "-bill_date", "-id"
    )

    if year_id:
        queryset = queryset.filter(academic_class__academic_year_id=year_id)
    elif current_year:
        queryset = queryset.filter(academic_class__academic_year=current_year)
    if term_id:
        queryset = queryset.filter(academic_class__term_id=term_id)
    elif current_term:
        queryset = queryset.filter(academic_class__term=current_term)
    if q:
        queryset = queryset.filter(
            Q(student__student_name__icontains=q)
            | Q(student__reg_no__icontains=q)
            | Q(student__schoolpay_code__icontains=q)
            | Q(student__contact__icontains=q)
        )

    rows = [_serialize_bill_row(bill) for bill in queryset[:2500]]
    if status_filter != "all":
        wanted = {
            "outstanding": "Outstanding",
            "partial": "Partial",
            "paid": "Paid",
            "credit": "Credit",
        }.get(status_filter)
        if wanted:
            rows = [row for row in rows if row["status"] == wanted]

    gross = sum((Decimal(row["gross_billed"]) for row in rows), Decimal("0"))
    adjustments = sum((Decimal(row["adjustments"]) for row in rows), Decimal("0"))
    paid = sum((Decimal(row["paid"]) for row in rows), Decimal("0"))
    outstanding = sum((Decimal(row["balance"]) for row in rows), Decimal("0"))
    credit = sum((Decimal(row["credit"]) for row in rows), Decimal("0"))

    years = list(AcademicYear.objects.order_by("-academic_year", "-id"))
    selected_year_id = int(year_id) if year_id and year_id.isdigit() else getattr(current_year, "id", None)
    terms = list(Term.objects.filter(academic_year_id=selected_year_id).order_by("term", "id")) if selected_year_id else []

    return {
        "title": "Student Accounts",
        "description": "Record payments against the student's actual bill, track part-payments, bursaries, overpayments and carry-forward credit.",
        "metrics": {
            "gross_billed": _money(gross),
            "adjustments": _money(adjustments),
            "paid": _money(paid),
            "outstanding": _money(outstanding),
            "credit": _money(credit),
        },
        "rows": rows,
        "filters": {
            "year": selected_year_id,
            "term": int(term_id) if term_id and term_id.isdigit() else getattr(current_term, "id", None),
            "status": status_filter,
            "q": q,
        },
        "years": [{"id": row.pk, "label": str(row)} for row in years],
        "terms": [{"id": row.pk, "label": str(row)} for row in terms],
        "actions": {"can_write": _can_write(request)},
    }


class StudentFinanceAPIView(WorkspaceBaseAPIView):
    def get(self, request, screen: str, pk: int | None = None):
        if not _can_read(request):
            record_finance_access_denial(request, "fees", operation="student_finance_read")
            return Response({"detail": "Your current role cannot access student finance."}, status=status.HTTP_403_FORBIDDEN)
        if screen == "accounts" and pk is None:
            return Response(_list_accounts(request))
        if screen == "account" and pk is not None:
            try:
                bill = StudentBill.objects.select_related(
                    "student", "student__current_class", "student__stream",
                    "academic_class__Class", "academic_class__academic_year", "academic_class__term",
                ).prefetch_related("items", "payments", "applied_credits", "fee_adjustments", "student__credits").get(pk=pk)
            except StudentBill.DoesNotExist:
                return Response({"detail": "Student fee account was not found."}, status=status.HTTP_404_NOT_FOUND)
            return Response(_serialize_account(bill, request))
        return Response({"detail": "Unknown student finance screen."}, status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    def post(self, request, screen: str, pk: int | None = None):
        if not _can_write(request):
            record_finance_access_denial(request, "fees", operation="student_finance_write")
            return Response({"detail": "Your current role cannot change student finance records."}, status=status.HTTP_403_FORBIDDEN)
        if screen != "account" or pk is None:
            return Response({"detail": "Unknown student finance action."}, status=status.HTTP_404_NOT_FOUND)

        try:
            bill = StudentBill.objects.select_for_update().select_related(
                "student", "student__current_class", "student__stream",
                "academic_class__Class", "academic_class__academic_year", "academic_class__term",
            ).get(pk=pk)
        except StudentBill.DoesNotExist:
            return Response({"detail": "Student fee account was not found."}, status=status.HTTP_404_NOT_FOUND)

        action = str(request.data.get("action") or "").strip().lower()
        username = request.user.get_username()

        if action == "record_payment":
            try:
                amount = _decimal(request.data.get("amount"), "Amount")
            except ValueError as exc:
                return Response({"detail": str(exc), "errors": {"amount": [str(exc)]}}, status=status.HTTP_400_BAD_REQUEST)
            payment_date = request.data.get("payment_date") or timezone.localdate().isoformat()
            method = str(request.data.get("payment_method") or "Cash").strip()
            reference = str(request.data.get("reference_no") or "").strip() or f"PMT-{bill.id}-{uuid4().hex[:16].upper()}"
            if Payment.objects.filter(reference_no=reference).exists():
                return Response({"detail": "That payment reference already exists.", "errors": {"reference_no": ["Reference must be unique."]}}, status=status.HTTP_400_BAD_REQUEST)
            payment = Payment.objects.create(
                bill=bill,
                payment_date=payment_date,
                amount=amount,
                payment_method=method,
                fee_category=str(request.data.get("fee_category") or ""),
                reference_no=reference,
                recorded_by=username,
                notes=str(request.data.get("notes") or ""),
            )
            _reconcile_overpayment_credit(bill)
            bill.refresh_from_db()
            return Response({
                "detail": "Payment recorded against the student's bill.",
                "payment": {
                    "id": payment.pk,
                    "reference": payment.reference_no,
                    "date": payment.payment_date.isoformat() if hasattr(payment.payment_date, "isoformat") else str(payment.payment_date),
                    "amount": _money(payment.amount),
                    "method": payment.payment_method,
                    "student": bill.student.student_name,
                    "student_number": bill.student.display_student_id,
                    "bill_id": bill.pk,
                    "class": str(bill.academic_class.Class),
                    "term": str(bill.academic_class.term),
                    "balance_after": _money(max(Decimal(bill.balance), Decimal("0"))),
                    "credit_after": _money(bill.available_credits),
                    "recorded_by": payment.recorded_by,
                    "school": _school_receipt_context(),
                },
                "account": _serialize_account(bill, request),
            }, status=status.HTTP_201_CREATED)

        if action == "add_adjustment":
            adjustment_type = str(request.data.get("adjustment_type") or StudentFeeAdjustment.TYPE_BURSARY)
            calculation_type = str(request.data.get("calculation_type") or StudentFeeAdjustment.CALC_FIXED)
            if adjustment_type not in ADJUSTMENT_TYPES:
                return Response({"detail": "Choose a valid bursary or adjustment type."}, status=status.HTTP_400_BAD_REQUEST)
            if calculation_type not in CALCULATION_TYPES:
                return Response({"detail": "Choose fixed amount or percentage."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                value = _decimal(request.data.get("value"), "Adjustment value")
            except ValueError as exc:
                return Response({"detail": str(exc), "errors": {"value": [str(exc)]}}, status=status.HTTP_400_BAD_REQUEST)
            gross = Decimal(bill.total_amount)
            requested_amount = (gross * value / Decimal("100")).quantize(Decimal("0.01")) if calculation_type == StudentFeeAdjustment.CALC_PERCENT else value
            remaining_adjustable = max(gross - Decimal(bill.approved_adjustments), Decimal("0"))
            if requested_amount > remaining_adjustable:
                return Response({"detail": f"This adjustment exceeds the remaining bill amount of UGX {_money(remaining_adjustable)}."}, status=status.HTTP_400_BAD_REQUEST)
            adjustment = StudentFeeAdjustment.objects.create(
                bill=bill,
                adjustment_type=adjustment_type,
                calculation_type=calculation_type,
                value=value,
                reason=str(request.data.get("reason") or ""),
                created_by=username,
                approved_by=username,
                status=StudentFeeAdjustment.STATUS_APPROVED,
            )
            _reconcile_overpayment_credit(bill)
            bill.refresh_from_db()
            return Response({
                "detail": f"{adjustment.adjustment_type} applied to the student's bill.",
                "adjustment_id": adjustment.pk,
                "account": _serialize_account(bill, request),
            }, status=status.HTTP_201_CREATED)

        if action == "cancel_adjustment":
            adjustment_id = request.data.get("adjustment_id")
            adjustment = bill.fee_adjustments.filter(pk=adjustment_id, status=StudentFeeAdjustment.STATUS_APPROVED).first()
            if not adjustment:
                return Response({"detail": "The adjustment was not found or is already cancelled."}, status=status.HTTP_404_NOT_FOUND)
            consumed_overpayment = StudentCredit.objects.filter(
                original_bill=bill,
                description__icontains="overpayment credit",
                is_applied=True,
            ).exists()
            if consumed_overpayment:
                return Response({"detail": "This adjustment cannot be cancelled because resulting overpayment credit has already been applied to another bill."}, status=status.HTTP_409_CONFLICT)
            adjustment.status = StudentFeeAdjustment.STATUS_CANCELLED
            adjustment.save(update_fields=["status"])
            _reconcile_overpayment_credit(bill)
            bill.refresh_from_db()
            return Response({"detail": "Fee adjustment cancelled.", "account": _serialize_account(bill, request)})

        if action == "apply_credit":
            requested = request.data.get("amount")
            try:
                amount = _decimal(requested, "Credit amount") if requested not in (None, "") else min(Decimal(bill.available_credits), max(Decimal(bill.balance), Decimal("0")))
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            applied = bill.apply_credit(amount)
            if applied <= 0:
                return Response({"detail": "There is no available credit that can be applied to this bill."}, status=status.HTTP_400_BAD_REQUEST)
            bill.refresh_from_db()
            return Response({"detail": f"UGX {_money(applied)} credit applied to this bill.", "account": _serialize_account(bill, request)})

        return Response({"detail": "Unknown student finance action."}, status=status.HTTP_400_BAD_REQUEST)
