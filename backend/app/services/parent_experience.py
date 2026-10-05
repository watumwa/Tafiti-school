"""Read-only presentation helpers for the authenticated parent experience."""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Avg, ExpressionWrapper, F, FloatField, Sum, Value

from app.models import (
    AttendanceRecord,
    ClassRegister,
    GradingSystem,
    LibraryFine,
    LibraryLoan,
    Result,
    Term,
    Timetable,
)


def current_academic_term():
    return Term.objects.filter(is_current=True).select_related("academic_year").order_by("id").first()


def percentage_expression():
    return ExpressionWrapper(
        F("score") * Value(100.0) / F("assessment__out_of"),
        output_field=FloatField(),
    )


def verified_results_for(student, term=None):
    results = Result.objects.filter(
        student=student,
        status="VERIFIED",
        assessment__out_of__gt=0,
    ).select_related(
        "assessment__subject",
        "assessment__assessment_type",
        "assessment__academic_class",
        "assessment__academic_class__term",
    )
    if term:
        results = results.filter(assessment__academic_class__term=term)
    return results


def attendance_for(student, term=None):
    records = AttendanceRecord.objects.filter(
        student=student,
        session__is_locked=True,
    ).exclude(status="unmarked").select_related(
        "session__subject",
        "session__term",
        "session__time_slot",
    )
    if term:
        records = records.filter(session__term=term)
    return records


def current_class_stream(student, term=None):
    registers = ClassRegister.objects.filter(student=student).select_related(
        "academic_class_stream__academic_class__academic_year",
        "academic_class_stream__academic_class__term",
        "academic_class_stream__academic_class__Class",
        "academic_class_stream__stream",
        "academic_class_stream__class_teacher",
    )
    if term:
        registers = registers.filter(academic_class_stream__academic_class__term=term)
    return registers.order_by("-academic_class_stream__academic_class__academic_year__academic_year", "-id").first()


def timetable_for_student(student, term=None, weekday=None):
    register = current_class_stream(student, term)
    if not register:
        return Timetable.objects.none(), None
    entries = Timetable.objects.filter(class_stream=register.academic_class_stream).select_related(
        "subject", "teacher", "time_slot", "classroom",
    ).order_by("weekday", "time_slot__start_time")
    if weekday:
        entries = entries.filter(weekday=weekday)
    return entries, register.academic_class_stream


def child_summary(access, term=None):
    student = access.student
    bills = list(
        student.bills.prefetch_related("items", "payments", "applied_credits").order_by("-bill_date")
        if access.can_view_finance else []
    )
    total_billed = sum((Decimal(str(bill.total_amount)) for bill in bills), Decimal("0"))
    total_paid = sum((Decimal(str(bill.amount_paid)) for bill in bills), Decimal("0"))
    balance = sum((Decimal(str(bill.balance)) for bill in bills), Decimal("0"))
    paid_percent = float(min(Decimal("100"), (total_paid / total_billed * 100))) if total_billed > 0 else None

    attendance = attendance_for(student, term) if access.can_view_attendance else AttendanceRecord.objects.none()
    attendance_total = attendance.count()
    present = attendance.filter(status__in=("present", "late")).count()
    attendance_percent = round((present / attendance_total) * 100, 1) if attendance_total else None

    results = verified_results_for(student, term) if access.can_view_academics else Result.objects.none()
    academic_average = results.aggregate(value=Avg(percentage_expression()))["value"] if access.can_view_academics else None

    active_loans = LibraryLoan.objects.filter(student=student, returned_at__isnull=True).select_related("copy__book")
    outstanding_fines = LibraryFine.objects.filter(
        loan__student=student,
        status=LibraryFine.STATUS_OUTSTANDING,
    ).aggregate(total=Sum("amount"))["total"]

    return {
        "access": access,
        "student": student,
        "bills": bills,
        "total_billed": total_billed,
        "total_paid": total_paid,
        "balance": balance,
        "paid_percent": paid_percent,
        "attendance_percent": attendance_percent,
        "attendance_total": attendance_total,
        "academic_average": academic_average,
        "active_loans": active_loans,
        "active_loan_count": active_loans.count(),
        "overdue_loan_count": sum(1 for loan in active_loans if loan.is_overdue),
        "outstanding_library_fines": outstanding_fines or Decimal("0"),
    }


def _grade_for_percentage(value, grade_bands):
    if value is None:
        return "—"
    for band in grade_bands:
        if float(band.min_score) <= float(value) <= float(band.max_score):
            return band.grade
    return "—"


def subject_performance(student, term=None):
    """Return normalized student/class averages and rank for each subject."""
    student_results = list(verified_results_for(student, term).order_by("assessment__date"))
    if not student_results:
        return []

    subject_ids = {result.assessment.subject_id for result in student_results}
    academic_class_ids = {result.assessment.academic_class_id for result in student_results}
    class_results = Result.objects.filter(
        status="VERIFIED",
        assessment__out_of__gt=0,
        assessment__subject_id__in=subject_ids,
        assessment__academic_class_id__in=academic_class_ids,
    ).select_related("assessment__subject", "assessment")

    student_values = defaultdict(list)
    class_values = defaultdict(list)
    per_student_subject = defaultdict(lambda: defaultdict(list))
    latest_dates = {}

    for result in class_results:
        percentage = float(result.score) * 100 / result.assessment.out_of
        subject_id = result.assessment.subject_id
        class_values[subject_id].append(percentage)
        per_student_subject[subject_id][result.student_id].append(percentage)
        if result.student_id == student.id:
            student_values[subject_id].append(percentage)
            latest_dates[subject_id] = max(latest_dates.get(subject_id, result.assessment.date), result.assessment.date)

    subjects = {result.assessment.subject_id: result.assessment.subject for result in student_results}
    grade_bands = list(GradingSystem.objects.order_by("min_score"))
    rows = []
    for subject_id, subject in subjects.items():
        values = student_values[subject_id]
        student_average = sum(values) / len(values) if values else None
        all_values = class_values[subject_id]
        class_average = sum(all_values) / len(all_values) if all_values else None
        ranked = sorted(
            (
                (candidate_id, sum(candidate_values) / len(candidate_values))
                for candidate_id, candidate_values in per_student_subject[subject_id].items()
                if candidate_values
            ),
            key=lambda item: (-item[1], item[0]),
        )
        rank = next((index for index, (candidate_id, _) in enumerate(ranked, start=1) if candidate_id == student.id), None)
        rows.append({
            "subject": subject,
            "average": student_average,
            "class_average": class_average,
            "rank": rank,
            "class_size": len(ranked),
            "grade": _grade_for_percentage(student_average, grade_bands),
            "assessment_count": len(values),
            "latest_date": latest_dates.get(subject_id),
            "difference": (student_average - class_average) if student_average is not None and class_average is not None else None,
        })
    return sorted(rows, key=lambda row: str(row["subject"]))
