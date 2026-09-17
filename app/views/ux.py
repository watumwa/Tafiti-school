"""UX-focused workflow views for daily school operations.

These views are intentionally small and conservative: they do not introduce new
business tables, so they can be deployed to an already-used school system without
migrating live data.
"""
from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from app.forms.fees_payment import PaymentForm
from app.models.accounts import StaffAccount
from app.models.classes import AcademicClass, AcademicClassStream, Class, Stream, Term
from app.models.fees_payment import BillItem, Payment, StudentBill
from app.models.results import Assessment, AssessmentType, GradingSystem, ResultBatch
from app.models.school_settings import AcademicYear, SchoolSetting, Signature
from app.models.staffs import Role, Staff
from app.models.students import Student
from app.models.subjects import Subject


ADMIN_ROLES = {"Admin", "Head Teacher", "Head master", "Headteacher"}
FINANCE_ROLES = ADMIN_ROLES | {"Bursar", "Finance", "Finance Manager"}
ACADEMIC_ROLES = ADMIN_ROLES | {"Director of Studies", "DOS", "Class Teacher", "Teacher"}


def _active_role(request) -> str:
    session_role = (request.session.get("active_role_name") or "").strip()
    if session_role:
        return session_role
    staff_account = getattr(request.user, "staff_account", None)
    if staff_account and getattr(staff_account, "role", None):
        return staff_account.role.name
    return "Support Staff"


def _role_key(role_name: str) -> str:
    return (role_name or "").strip().lower().replace("_", "-")


def _has_any_role(request, roles) -> bool:
    if getattr(request.user, "is_superuser", False):
        return True
    active = _active_role(request)
    if active in roles:
        return True
    try:
        return request.user.staff_account.staff.roles.filter(name__in=list(roles)).exists()
    except Exception:
        return False


def _money(value):
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _latest_current_scope():
    current_year = AcademicYear.objects.filter(is_current=True).first()
    current_term = Term.objects.filter(is_current=True).select_related("academic_year").first()
    return current_year, current_term


@login_required
def bursar_quick_payment_view(request):
    """Fast payment workflow: search learner, pick bill, record money."""
    if not _has_any_role(request, FINANCE_ROLES):
        messages.error(request, "Only Admin, Head Teacher, Bursar or Finance users can record payments.")
        return redirect("index_page")

    query = (request.GET.get("q") or "").strip()
    selected_student_id = (request.GET.get("student") or "").strip()
    selected_bill_id = request.POST.get("bill") or request.GET.get("bill")

    students = []
    selected_student = None
    bills = []
    selected_bill = None
    payment_form = None

    if query:
        students = list(
            Student.objects.filter(
                Q(student_name__icontains=query)
                | Q(reg_no__icontains=query)
                | Q(guardian__icontains=query)
                | Q(contact__icontains=query)
            ).select_related("current_class", "stream").order_by("student_name")[:12]
        )

    if selected_student_id:
        selected_student = get_object_or_404(Student.objects.select_related("current_class", "stream"), pk=selected_student_id)
        bills = list(
            StudentBill.objects.filter(student=selected_student)
            .select_related("academic_class", "academic_class__Class", "academic_class__term")
            .order_by("-bill_date")
        )
        if selected_bill_id:
            selected_bill = get_object_or_404(StudentBill, pk=selected_bill_id, student=selected_student)
        elif bills:
            selected_bill = next((bill for bill in bills if _money(bill.balance) > 0), bills[0])

    if request.method == "POST" and selected_bill:
        payment_form = PaymentForm(request.POST, bill=selected_bill)
        if payment_form.is_valid():
            with transaction.atomic():
                locked_bill = StudentBill.objects.select_for_update().get(pk=selected_bill.pk)
                payment = payment_form.save(commit=False)
                payment.bill = locked_bill
                payment.recorded_by = getattr(request.user, "username", "") or request.user.get_username()
                if not getattr(payment, "reference_no", None) or str(payment.reference_no).strip() == "":
                    payment.reference_no = f"PMT-{locked_bill.id}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
                payment.save()
                locked_bill.status = "Paid" if _money(locked_bill.balance) <= 0 else "Unpaid"
                locked_bill.save(update_fields=["status"])
            messages.success(request, f"Payment of UGX {payment.amount:,.0f} recorded for {selected_student.student_name}.")
            return redirect(f"{reverse('quick_payment')}?student={selected_student.id}&bill={selected_bill.id}")
        messages.error(request, "Please correct the payment details and try again.")
    elif selected_bill:
        payment_form = PaymentForm(
            bill=selected_bill,
            initial={"payment_date": timezone.localdate(), "amount": selected_bill.balance if _money(selected_bill.balance) > 0 else None},
        )

    totals = {
        "total_billed": Decimal("0"),
        "total_paid": Decimal("0"),
        "balance": Decimal("0"),
    }
    if selected_student:
        total_billed = StudentBill.objects.filter(student=selected_student).aggregate(total=Sum("items__amount"))["total"] or 0
        total_paid = Payment.objects.filter(bill__student=selected_student).aggregate(total=Sum("amount"))["total"] or 0
        totals = {
            "total_billed": _money(total_billed),
            "total_paid": _money(total_paid),
            "balance": sum((_money(bill.balance) for bill in bills), Decimal("0")),
        }

    recent_payments = []
    if selected_student:
        recent_payments = list(
            Payment.objects.filter(bill__student=selected_student)
            .select_related("bill")
            .order_by("-payment_date", "-id")[:8]
        )

    return render(request, "fees/quick_payment.html", {
        "query": query,
        "students": students,
        "selected_student": selected_student,
        "bills": bills,
        "selected_bill": selected_bill,
        "payment_form": payment_form,
        "totals": totals,
        "recent_payments": recent_payments,
        "selected_bill_has_balance": bool(selected_bill and _money(selected_bill.balance) > 0),
    })
