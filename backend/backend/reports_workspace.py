from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from app.models import (
    AdmissionApplication,
    AttendanceRecord,
    BankStatement,
    BankTransaction,
    Budget,
    Expenditure,
    FeeRefund,
    LibraryFine,
    LibraryLoan,
    Payment,
    Result,
    SchoolSetting,
    Staff,
    StaffLeave,
    StaffSalaryHistory,
    Student,
    StudentBill,
    StudentLifecycleEvent,
    Transaction,
)

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context


REPORT_ACCESS = {
    "academics": {"Admin", "Head Teacher", "Director of Studies", "Teacher", "Class Teacher"},
    "attendance": {"Admin", "Head Teacher", "Director of Studies", "Teacher", "Class Teacher"},
    "finance": {"Admin", "Head Teacher", "Bursar"},
    "admissions": {"Admin", "Head Teacher", "Admissions Officer"},
    "library": {"Admin", "Head Teacher", "Librarian"},
    "hr": {"Admin", "Head Teacher", "Director of Studies"},
    "students": {"Admin", "Head Teacher", "Director of Studies", "Admissions Officer"},
}


def _role(request):
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _money(value):
    return f"{Decimal(value or 0):.2f}"


def _borrower_name(loan):
    return str(loan.student or loan.staff or "Unknown borrower")


def _rank_rows(rows, score_key="score"):
    school = SchoolSetting.load()
    if not school.show_report_positions or school.report_ranking_method == SchoolSetting.RankingMethod.NONE:
        return rows
    sorted_rows = sorted(rows, key=lambda row: Decimal(str(row.get(score_key) or 0)), reverse=True)
    previous_score = None
    previous_position = 0
    dense_position = 0
    for index, row in enumerate(sorted_rows, start=1):
        current_score = Decimal(str(row.get(score_key) or 0))
        if previous_score is None or current_score != previous_score:
            dense_position += 1
            previous_position = index if school.report_tie_policy == SchoolSetting.TiePolicy.COMPETITION else dense_position
        row["position"] = previous_position
        previous_score = current_score
    return sorted_rows


def _academics(report):
    verified = Result.objects.filter(status="VERIFIED", assessment__subject__show_on_report=True).select_related(
        "student", "assessment__subject", "assessment__academic_class__Class", "assessment__academic_class__term"
    )
    computed = verified.filter(assessment__subject__include_in_totals=True)
    if report == "student-performance":
        grouped = computed.values("student_id", "student__student_name", "student__reg_no").annotate(
            average=Avg("score"), total=Sum("score"), results=Count("id")
        )
        school = SchoolSetting.load()
        rows = [
            {
                "student_id": row["student_id"], "student": row["student__student_name"], "reg_no": row["student__reg_no"],
                "average": f"{Decimal(row['average'] or 0):.2f}", "total": f"{Decimal(row['total'] or 0):.2f}", "results": row["results"],
                "score": Decimal(row["average"] or 0) if school.report_ranking_method == SchoolSetting.RankingMethod.AVERAGE else Decimal(row["total"] or 0),
            }
            for row in grouped
        ]
        rows = _rank_rows(rows)
    elif report == "subject-performance":
        rows = [
            {
                "subject": row["assessment__subject__name"],
                "average": f"{Decimal(row['average'] or 0):.2f}",
                "results": row["results"],
                "computed": bool(row["assessment__subject__include_in_totals"]),
            }
            for row in verified.values("assessment__subject__name", "assessment__subject__include_in_totals").annotate(average=Avg("score"), results=Count("id")).order_by("-average")
        ]
    else:
        rows = [
            {"class": row["assessment__academic_class__Class__name"], "average": f"{Decimal(row['average'] or 0):.2f}", "results": row["results"]}
            for row in computed.values("assessment__academic_class__Class__name").annotate(average=Avg("score"), results=Count("id")).order_by("-average")
        ]
    return {"category": "Academics", "report": report, "rows": rows, "count": len(rows)}


def _attendance(report):
    records = AttendanceRecord.objects.select_related("student", "session__class_stream__academic_class__Class", "session")
    if report == "absenteeism":
        rows = [
            {"student": row["student__student_name"], "reg_no": row["student__reg_no"], "absences": row["absences"]}
            for row in records.filter(status="absent").values("student__student_name", "student__reg_no").annotate(absences=Count("id")).order_by("-absences")
        ]
    elif report == "class":
        rows = []
        for row in records.values("session__class_stream__academic_class__Class__name").annotate(total=Count("id"), present=Count("id", filter=Q(status__in=("present", "late")))):
            total = row["total"] or 0
            rows.append({"class": row["session__class_stream__academic_class__Class__name"], "marked": total, "present": row["present"], "attendance_percent": round((row["present"] / total) * 100, 1) if total else 0})
    else:
        period = report if report in {"daily", "weekly", "monthly"} else "daily"
        today = timezone.localdate()
        if period == "weekly":
            start = today - timedelta(days=6)
        elif period == "monthly":
            start = today.replace(day=1)
        else:
            start = today
        rows = [
            {"date": str(row["session__date"]), "status": row["status"], "count": row["count"]}
            for row in records.filter(session__date__gte=start, session__date__lte=today).values("session__date", "status").annotate(count=Count("id")).order_by("session__date", "status")
        ]
    return {"category": "Attendance", "report": report, "rows": rows, "count": len(rows)}


def _financial_statement():
    fee_collections = Payment.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    other_income = Transaction.objects.filter(transaction_type="Income").aggregate(total=Sum("amount"))["total"] or Decimal("0")
    direct_expenses = Transaction.objects.filter(transaction_type="Expense").aggregate(total=Sum("amount"))["total"] or Decimal("0")
    expenditures = Decimal("0")
    for expenditure in Expenditure.objects.prefetch_related("items"):
        expenditures += Decimal(expenditure.amount or 0)

    billed = Decimal("0")
    receivables = Decimal("0")
    credits = Decimal("0")
    for bill in StudentBill.objects.prefetch_related("items", "payments", "fee_adjustments", "applied_credits"):
        billed += Decimal(bill.net_amount_due or 0)
        balance = Decimal(bill.balance or 0)
        if balance > 0:
            receivables += balance
        elif balance < 0:
            credits += abs(balance)

    total_income = Decimal(fee_collections) + Decimal(other_income)
    total_expenses = Decimal(direct_expenses) + expenditures
    net_movement = total_income - total_expenses
    rows = [
        {"section": "Income", "item": "School fee collections", "amount": _money(fee_collections)},
        {"section": "Income", "item": "Other recorded income", "amount": _money(other_income)},
        {"section": "Income", "item": "Total cash income", "amount": _money(total_income)},
        {"section": "Expenses", "item": "Budget-linked expenditure", "amount": _money(expenditures)},
        {"section": "Expenses", "item": "Other expense transactions", "amount": _money(direct_expenses)},
        {"section": "Expenses", "item": "Total expenses", "amount": _money(total_expenses)},
        {"section": "Position", "item": "Net cash movement", "amount": _money(net_movement)},
        {"section": "Position", "item": "Net fees billed after adjustments", "amount": _money(billed)},
        {"section": "Position", "item": "Outstanding fee receivables", "amount": _money(receivables)},
        {"section": "Position", "item": "Student credit balances", "amount": _money(credits)},
    ]
    return rows


def _reconciliation_rows():
    rows = []
    for statement in BankStatement.objects.select_related("bank_account").prefetch_related("transactions").order_by("-statement_date", "-id"):
        transactions = list(statement.transactions.all())
        credits = sum((Decimal(row.amount or 0) for row in transactions if row.transaction_type == "Credit"), Decimal("0"))
        debits = sum((Decimal(row.amount or 0) for row in transactions if row.transaction_type == "Debit"), Decimal("0"))
        reconciled = [row for row in transactions if row.reconciled]
        rows.append({
            "statement": str(statement),
            "account": str(statement.bank_account),
            "date": statement.statement_date.isoformat(),
            "opening": _money(statement.opening_balance),
            "credits": _money(credits),
            "debits": _money(debits),
            "closing": _money(statement.closing_balance),
            "transactions": len(transactions),
            "reconciled": len(reconciled),
            "unreconciled": len(transactions) - len(reconciled),
        })
    return rows


def _finance(report):
    bills = list(StudentBill.objects.select_related("student", "academic_class__Class", "academic_class__term"))
    if report in {"financial-statement", "statement", "income-expense"}:
        rows = _financial_statement()
    elif report in {"reconciliation", "bank-reconciliation"}:
        rows = _reconciliation_rows()
    elif report in {"debtors", "aging", "outstanding"}:
        rows = []
        today = timezone.localdate()
        for bill in bills:
            balance = Decimal(bill.balance or 0)
            if balance <= 0:
                continue
            age = max((today - bill.bill_date).days, 0)
            band = "0-30" if age <= 30 else "31-60" if age <= 60 else "61-90" if age <= 90 else "90+"
            rows.append({"student": bill.student.student_name, "reg_no": bill.student.reg_no, "class": str(bill.academic_class.Class), "bill_date": bill.bill_date.isoformat(), "balance": _money(balance), "age_days": age, "aging_band": band})
    elif report == "methods":
        rows = [{"method": row["payment_method"], "transactions": row["count"], "amount": _money(row["amount"])} for row in Payment.objects.values("payment_method").annotate(count=Count("id"), amount=Sum("amount")).order_by("payment_method")]
    elif report == "cashier-closing":
        today = timezone.localdate()
        rows = [{"recorded_by": row["recorded_by"] or "Unknown", "transactions": row["count"], "amount": _money(row["amount"])} for row in Payment.objects.filter(payment_date=today).values("recorded_by").annotate(count=Count("id"), amount=Sum("amount")).order_by("recorded_by")]
    elif report == "refunds":
        rows = [{"id": row.pk, "student": row.payment.bill.student.student_name, "amount": _money(row.amount), "status": row.get_status_display(), "reason": row.reason} for row in FeeRefund.objects.select_related("payment__bill__student")]
    elif report == "budget-variance":
        rows = []
        for budget in Budget.objects.prefetch_related("budget_items__budget_expenditures__items"):
            allocated = sum((Decimal(item.allocated_amount or 0) for item in budget.budget_items.all()), Decimal("0"))
            spent = sum((Decimal(item.amount_spent or 0) for item in budget.budget_items.all()), Decimal("0"))
            rows.append({"budget": str(budget), "allocated": _money(allocated), "spent": _money(spent), "variance": _money(allocated-spent)})
    else:
        rows = [{"date": str(row["payment_date"]), "transactions": row["count"], "amount": _money(row["amount"])} for row in Payment.objects.values("payment_date").annotate(count=Count("id"), amount=Sum("amount")).order_by("-payment_date")[:180]]
    return {"category": "Finance", "report": report, "rows": rows, "count": len(rows)}


def _admissions(report):
    applications = AdmissionApplication.objects.all()
    counts = {row["status"]: row["count"] for row in applications.values("status").annotate(count=Count("id"))}
    total = applications.count()
    enrolled = counts.get(AdmissionApplication.STATUS_ENROLLED, 0)
    if report == "conversion":
        rows = [{"metric": "Applications", "value": total}, {"metric": "Enrolled", "value": enrolled}, {"metric": "Conversion rate", "value": round((enrolled/total)*100, 1) if total else 0}]
    else:
        wanted = {"enrolled": AdmissionApplication.STATUS_ENROLLED, "rejected": AdmissionApplication.STATUS_REJECTED, "waitlisted": AdmissionApplication.STATUS_WAITLISTED}.get(report)
        qs = applications.filter(status=wanted) if wanted else applications
        rows = [{"reference": row.application_number, "student": row.student_name, "status": row.get_status_display(), "class": str(row.applying_class), "created_at": row.created_at.isoformat()} for row in qs.select_related("applying_class")[:1000]]
    return {"category": "Admissions", "report": report, "rows": rows, "count": len(rows), "pipeline": counts}


def _library(report):
    loans = LibraryLoan.objects.select_related("copy__book", "student", "staff")
    now = timezone.now()
    if report == "overdue":
        qs = loans.filter(returned_at__isnull=True, due_at__lt=now)
        rows = [{"book": row.copy.book.title, "borrower": _borrower_name(row), "due_at": row.due_at.isoformat(), "days_overdue": max((now-row.due_at).days, 0)} for row in qs]
    elif report == "fines":
        rows = [{"book": row.loan.copy.book.title, "borrower": _borrower_name(row.loan), "reason": row.get_reason_display(), "amount": _money(row.amount), "status": row.get_status_display()} for row in LibraryFine.objects.select_related("loan__copy__book", "loan__student", "loan__staff")]
    elif report == "popular":
        rows = [{"book": row["copy__book__title"], "borrows": row["borrows"]} for row in loans.values("copy__book__title").annotate(borrows=Count("id")).order_by("-borrows")[:100]]
    else:
        qs = loans.filter(returned_at__isnull=True)
        rows = [{"book": row.copy.book.title, "borrower": _borrower_name(row), "issued_at": row.issued_at.isoformat(), "due_at": row.due_at.isoformat()} for row in qs]
    return {"category": "Library", "report": report, "rows": rows, "count": len(rows)}


def _hr(report):
    if report == "leave":
        rows = [{"staff": str(row.staff), "type": row.leave_type, "start": row.start_date.isoformat(), "end": row.end_date.isoformat(), "status": row.get_status_display()} for row in StaffLeave.objects.select_related("staff")]
    elif report == "salary-history":
        rows = [{"staff": str(row.staff), "amount": _money(row.amount), "effective_from": row.effective_from.isoformat(), "reason": row.reason} for row in StaffSalaryHistory.objects.select_related("staff")]
    else:
        rows = [{"id": row.pk, "staff": str(row), "department": row.get_department_display(), "qualification": row.qualification, "status": row.get_staff_status_display(), "salary": _money(row.salary)} for row in Staff.objects.prefetch_related("roles")]
    return {"category": "HR & Staff", "report": report, "rows": rows, "count": len(rows)}


def _students(report):
    if report == "lifecycle":
        rows = [{"student": row.student.student_name, "reg_no": row.student.reg_no, "status": row.get_status_display(), "effective_date": row.effective_date.isoformat(), "reason": row.reason} for row in StudentLifecycleEvent.objects.select_related("student")]
    else:
        rows = [{"id": row.pk, "student": row.student_name, "reg_no": row.reg_no, "lin": row.lin_number or "", "schoolpay": row.schoolpay_number or "", "student_type": row.residency_status, "class": str(row.current_class), "stream": str(row.stream), "active": row.is_active} for row in Student.objects.select_related("current_class", "stream")]
    return {"category": "Students", "report": report, "rows": rows, "count": len(rows)}


class ReportsWorkspaceAPIView(WorkspaceBaseAPIView):
    def get(self, request, category: str):
        category = category.lower().strip()
        if category not in REPORT_ACCESS:
            return Response({"detail": "Unknown report category."}, status=status.HTTP_404_NOT_FOUND)
        if not request.user.is_superuser and _role(request) not in REPORT_ACCESS[category]:
            return Response({"detail": "Your current role cannot access this report category."}, status=status.HTTP_403_FORBIDDEN)
        report = str(request.query_params.get("report") or "summary").strip().lower()
        handlers = {
            "academics": _academics,
            "attendance": _attendance,
            "finance": _finance,
            "admissions": _admissions,
            "library": _library,
            "hr": _hr,
            "students": _students,
        }
        payload = handlers[category](report)
        payload["generated_at"] = timezone.now().isoformat()
        payload["role"] = _role(request)
        return Response(payload)
