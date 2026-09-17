"""Overview service for the admin control-tower dashboard."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone

from app.models.attendance import AttendanceRecord, AttendanceSession, AttendanceStatus
from app.models.classes import AcademicClassStream
from app.models.fees_payment import Payment, StudentBill, StudentBillItem
from app.models.results import ResultBatch
from app.models.staffs import Staff
from app.models.timetables import Timetable
from app.services.level_scope import get_level_academic_classes_queryset, get_level_students_queryset
from app.services.school_level import get_active_school_level

WEEKDAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def _weekday_code(for_date):
    return WEEKDAY_CODES[for_date.weekday()]


def _percent(part: float, whole: float) -> float:
    if not whole:
        return 0
    return round((part / whole) * 100, 1)


def _attendance_rate(queryset) -> float:
    total = queryset.count()
    if not total:
        return 0
    present_like = queryset.filter(
        status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE]
    ).count()
    return _percent(present_like, total)


def get_overview_context(request, scope):
    """Executive summary cards and top operational alerts."""
    current_year = scope.get("current_year")
    current_term = scope.get("current_term")
    active_level = get_active_school_level(request)
    scoped_students = get_level_students_queryset(active_level=active_level)
    today = timezone.localdate()
    week_start = today - timedelta(days=6)

    total_students_active = scoped_students.filter(is_active=True).count()
    total_students_inactive = scoped_students.filter(is_active=False).count()
    total_teachers = (
        Staff.objects.filter(
            Q(roles__name__in=["Teacher", "Class Teacher"]) | Q(is_academic_staff=True)
        )
        .distinct()
        .count()
    )

    if current_year and current_term:
        scoped_academic_classes = get_level_academic_classes_queryset(
            active_level=active_level
        ).filter(
            academic_year=current_year, term=current_term
        )
        total_classes = scoped_academic_classes.count()
        total_streams = AcademicClassStream.objects.filter(
            academic_class__in=scoped_academic_classes,
        ).count()
        total_fees_expected = (
            StudentBillItem.objects.filter(
                bill__student__is_active=True,
                bill__academic_class__in=scoped_academic_classes,
                bill__academic_class__academic_year=current_year,
                bill__academic_class__term=current_term,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        total_fees_collected = (
            Payment.objects.filter(
                bill__student__is_active=True,
                bill__academic_class__in=scoped_academic_classes,
                bill__academic_class__academic_year=current_year,
                bill__academic_class__term=current_term,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )

        attendance_scope = AttendanceRecord.objects.filter(
            session__academic_year=current_year,
            session__term=current_term,
            session__is_locked=True,
            session__class_stream__academic_class__in=scoped_academic_classes,
        )
        attendance_today_rate = _attendance_rate(attendance_scope.filter(session__date=today))
        attendance_week_rate = _attendance_rate(
            attendance_scope.filter(session__date__range=(week_start, today))
        )

        overdue_bills_count = StudentBill.objects.filter(
            student__is_active=True,
            academic_class__in=scoped_academic_classes,
            academic_class__academic_year=current_year,
            academic_class__term=current_term,
            status="Overdue",
        ).count()
        verification_pending_count = ResultBatch.objects.filter(
            status="PENDING",
            assessment__academic_class__in=scoped_academic_classes,
            assessment__academic_class__academic_year=current_year,
            assessment__academic_class__term=current_term,
        ).count()
        submitted_stream_ids_today = set(
            AttendanceSession.objects.filter(
                academic_year=current_year,
                term=current_term,
                date=today,
                is_locked=True,
                class_stream__academic_class__in=scoped_academic_classes,
            )
            .values_list("class_stream_id", flat=True)
            .distinct()
        )
        submitted_streams_today = len(submitted_stream_ids_today)
        scheduled_stream_ids = set(
            Timetable.objects.filter(
                class_stream__academic_class__in=scoped_academic_classes,
                weekday=_weekday_code(today),
            )
            .values_list("class_stream_id", flat=True)
            .distinct()
        )
        if scheduled_stream_ids:
            expected_streams_today = len(scheduled_stream_ids | submitted_stream_ids_today)
        else:
            expected_streams_today = total_streams
        missing_attendance_streams = max(expected_streams_today - submitted_streams_today, 0)
    else:
        total_classes = 0
        total_streams = 0
        total_fees_expected = 0
        total_fees_collected = 0
        attendance_today_rate = 0
        attendance_week_rate = 0
        overdue_bills_count = 0
        verification_pending_count = 0
        missing_attendance_streams = 0

    outstanding_fees = max(total_fees_expected - total_fees_collected, 0)
    collection_rate = _percent(total_fees_collected, total_fees_expected)
    outstanding_rate = _percent(outstanding_fees, total_fees_expected)
    operational_health_score = round(
        (collection_rate + attendance_today_rate + attendance_week_rate) / 3, 1
    ) if total_fees_expected or attendance_today_rate or attendance_week_rate else 0

    overview_finance_labels = ["Collected", "Outstanding"]
    overview_finance_values = [float(total_fees_collected or 0), float(outstanding_fees or 0)]
    overview_operations_labels = ["Students", "Teachers", "Classes", "Streams"]
    overview_operations_values = [
        total_students_active,
        total_teachers,
        total_classes,
        total_streams,
    ]
    overview_attendance_labels = ["Today", "This Week"]
    overview_attendance_values = [attendance_today_rate, attendance_week_rate]
    overview_risk_labels = ["Overdue Bills", "Verification Pending", "Attendance Gaps"]
    overview_risk_values = [
        overdue_bills_count,
        verification_pending_count,
        missing_attendance_streams,
    ]

    alerts = [
        {
            "label": "Overdue fee bills",
            "count": overdue_bills_count,
            "severity": "danger",
            "url": reverse("fees_status"),
        },
        {
            "label": "Verification queue pending",
            "count": verification_pending_count,
            "severity": "warning",
            "url": reverse("verification_overview"),
        },
        {
            "label": "Class streams missing today's attendance",
            "count": missing_attendance_streams,
            "severity": "warning",
            "url": reverse("attendance_dashboard"),
        },
        {
            "label": "Outstanding balances",
            "count": round(outstanding_fees, 2),
            "severity": "danger" if outstanding_fees else "ok",
            "url": reverse("fees_status"),
        },
    ]
    alerts = [alert for alert in alerts if alert["count"]]

    quick_actions = [
        {"label": "Add Student", "icon": "fa-user-plus", "url": reverse("add_student")},
        {"label": "Student Bills", "icon": "fa-money", "url": reverse("student_bill_page")},
        {"label": "Create Class", "icon": "fa-university", "url": reverse("class_page")},
        {"label": "Register Staff", "icon": "fa-id-badge", "url": reverse("add_staff")},
        {"label": "Run Reports", "icon": "fa-file-text", "url": reverse("class_stream_filter")},
        {
            "label": "Post Announcement",
            "icon": "fa-bullhorn",
            "url": reverse("announcement_create"),
        },
    ]

    return {
        "total_students_active": total_students_active,
        "total_students_inactive": total_students_inactive,
        "total_teachers": total_teachers,
        "total_classes": total_classes,
        "total_streams": total_streams,
        "total_fees_expected": total_fees_expected,
        "total_fees_collected": total_fees_collected,
        "outstanding_fees": outstanding_fees,
        "collection_rate": collection_rate,
        "outstanding_rate": outstanding_rate,
        "operational_health_score": operational_health_score,
        "attendance_today_rate": attendance_today_rate,
        "attendance_week_rate": attendance_week_rate,
        "overview_alerts": alerts,
        "overview_quick_actions": quick_actions,
        "overview_finance_labels": overview_finance_labels,
        "overview_finance_values": overview_finance_values,
        "overview_operations_labels": overview_operations_labels,
        "overview_operations_values": overview_operations_values,
        "overview_attendance_labels": overview_attendance_labels,
        "overview_attendance_values": overview_attendance_values,
        "overview_risk_labels": overview_risk_labels,
        "overview_risk_values": overview_risk_values,
    }
