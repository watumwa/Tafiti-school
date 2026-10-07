from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from math import ceil
from typing import Any, Callable

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from app.models import (
    AcademicClass,
    AcademicYear,
    AdmissionApplication,
    Announcement,
    Assessment,
    AttendanceRecord,
    AttendanceSession,
    AuditLog,
    BankTransaction,
    Budget,
    BudgetItem,
    BillItem,
    ClassRegister,
    ClassBill,
    ClassSubjectAllocation,
    Expense,
    Event,
    Expenditure,
    ExpenditureItem,
    LibraryBook,
    LibraryCopy,
    LibraryFine,
    LibraryLoan,
    IncomeSource,
    ParentAccess,
    ParentNotification,
    Payment,
    Result,
    ResultBatch,
    ResultVerificationNotification,
    SchoolSetting,
    Staff,
    Student,
    StudentCredit,
    StudentBill,
    Subject,
    Term,
    Timetable,
    Vendor,
)

from .auth import assigned_role_labels, canonical_role_label, resolve_active_role, serialize_user_context


# The navigation is deliberately generated server-side.  Hiding a link in the
# browser is not authorization; the same registry is used to reject API calls.
# Navigation is organised around the small number of operational workspaces
# staff use every day. The role/resource checks below remain the security
# boundary; this registry only decides how permitted work is presented.
NAVIGATION = {
    "control_tower": [
        {"slug": "overview", "label": "Dashboard", "icon": "layout-dashboard", "resource": None},
        {"slug": "analytics", "path": "reports", "label": "Analytics", "icon": "chart-no-axes-column", "resource": "results"},
    ],
    "administration": [
        {"slug": "admissions", "label": "Admissions", "icon": "user-plus", "resource": "admissions"},
        {"slug": "students", "label": "Student Directory", "icon": "users", "resource": "students"},
        {"slug": "staff", "label": "Staff & Roles", "icon": "badge-check", "resource": "staff"},
        {"slug": "system-administration", "label": "System Administration", "icon": "settings-2", "resource": None, "roles": ["Admin"]},
    ],
    "academics": [
        {"slug": "academic-setup", "label": "Academic Setup", "icon": "school", "resource": None, "roles": ["Admin", "Head Teacher", "Director of Studies", "Teacher", "Class Teacher"]},
        {"slug": "timetable", "label": "Timetable", "icon": "calendar-days", "resource": "timetable"},
        {"slug": "attendance", "label": "Attendance", "icon": "calendar-check", "resource": "attendance"},
        {"slug": "results", "label": "Assessments & Results", "icon": "clipboard-pen-line", "resource": "results"},
        {"slug": "library", "label": "Library", "icon": "library", "resource": "library"},
    ],
    "finance": [
        {"slug": "fees", "label": "Fees & Payments", "icon": "wallet-cards", "resource": "fees"},
        {"slug": "finance", "label": "Finance Management", "icon": "landmark", "resource": "finance"},
    ],
    "communication": [
        {"slug": "communication", "label": "Messages & Notices", "icon": "messages-square", "resource": "communication"},
    ],
}

ROLE_RESOURCES = {
    "Admin": {"*"},
    "Head Teacher": {"*"},
    "Director of Studies": {
        "students", "staff", "admissions", "parents", "classes", "subjects", "results",
        "attendance", "timetable", "communication", "audit",
    },
    "Bursar": {
        "students", "fees", "fees-payments", "fees-class-bills", "fees-bill-items",
        "finance", "finance-budgets", "finance-expenses", "finance-vendors",
        "finance-income", "finance-budget-items", "finance-expenditure-items",
        "communication", "audit",
    },
    "Class Teacher": {"students", "classes", "subjects", "results", "attendance", "timetable", "communication"},
    "Teacher": {"students", "classes", "subjects", "results", "attendance", "timetable", "communication"},
    "Admissions Officer": {"students", "admissions", "communication"},
    "Librarian": {"students", "library", "communication"},
    "Library Assistant": {"students", "library", "communication"},
    "Support Staff": {"communication"},
    "Parent": {
        "students", "results", "attendance", "fees", "communication",
        "parent-profile", "parent-children", "parent-results", "parent-attendance",
        "parent-finance", "parent-communication", "parent-calendar",
        "parent-notifications", "parent-reports",
    },
    "Staff": {"communication"},
}

GROUP_LABELS = {
    "control_tower": "Control Tower",
    "administration": "Administration",
    "academics": "Academics",
    "finance": "Finance",
    "communication": "Communication",
}


FINANCIAL_RESOURCES = frozenset({
    "fees", "fees-payments", "fees-class-bills", "fees-bill-items",
    "finance", "finance-budgets", "finance-budget-items",
    "finance-expenditure-items", "finance-expenses", "finance-vendors",
    "finance-income",
})
FINANCE_BLIND_SPOT_ROLES = frozenset({"Teacher", "Class Teacher", "Director of Studies"})


def _str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(value)


def _date(value: Any) -> str:
    return value.isoformat() if value else ""


def _money(value: Any) -> str:
    try:
        return f"{Decimal(value or 0):.2f}"
    except Exception:
        return "0.00"


def _safe_file_url(file_value: Any) -> str:
    if not file_value:
        return ""
    try:
        return file_value.url
    except Exception:
        return ""


def _token_context(request) -> str | None:
    auth = getattr(request, "auth", None)
    if auth is None:
        return None
    try:
        return auth.get("portal_context")
    except Exception:
        return None


def _active_role(request) -> str:
    return resolve_active_role(request.user, _token_context(request)).label


def _allowed_resources(request) -> set[str]:
    if request.user.is_superuser:
        return {"*"}
    role = canonical_role_label(_active_role(request))
    if role == "Parent":
        accesses = _parent_accesses(request.user)
        allowed = {"students", "communication"}
        if accesses.filter(can_view_academics=True).exists():
            allowed.add("results")
        if accesses.filter(can_view_attendance=True).exists():
            allowed.add("attendance")
        if accesses.filter(can_view_finance=True).exists():
            allowed.add("fees")
        return allowed
    return ROLE_RESOURCES.get(role, set())


def _can_access(request, resource: str) -> bool:
    allowed = _allowed_resources(request)
    return "*" in allowed or resource in allowed


def record_finance_access_denial(request, resource: str, *, operation: str) -> None:
    """Record intentional finance access attempts from academic-only roles.

    Financial resources are denied by ``_can_access`` before this helper runs;
    the audit entry preserves that security signal without returning audit
    implementation details to the requester.
    """
    role = canonical_role_label(_active_role(request))
    if resource not in FINANCIAL_RESOURCES or role not in FINANCE_BLIND_SPOT_ROLES:
        return

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    client_ip = forwarded_for.split(",")[0].strip() or request.META.get("REMOTE_ADDR") or None
    try:
        AuditLog.objects.create(
            user=request.user,
            username=request.user.get_username(),
            ip_address=client_ip,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:4000],
            method=request.method,
            path=request.get_full_path()[:512],
            action=AuditLog.ACTION_UPDATE,
            object_repr="Denied finance access",
            changes=None,
            extra={
                "security_event": "finance_access_denied",
                "resource": resource,
                "operation": operation,
                "role": role,
            },
        )
    except Exception:
        # An audit-write issue must never turn a protected finance endpoint
        # into an available one or disclose logging internals to the requester.
        return


def _staff_for_user(user):
    try:
        return user.staff_account.staff
    except Exception:
        return None


def _parent_accesses(user):
    return ParentAccess.objects.filter(user=user, is_active=True, is_verified=True).select_related("student")


def _parent_student_ids(user) -> list[int]:
    return list(_parent_accesses(user).values_list("student_id", flat=True))


def _is_parent_context(request) -> bool:
    return canonical_role_label(_active_role(request)) == "Parent"


def _scope_students(request, queryset):
    role = canonical_role_label(_active_role(request))
    if role == "Parent":
        return queryset.filter(pk__in=_parent_student_ids(request.user))
    if role in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        if not staff:
            return queryset.none()
        allocations = ClassSubjectAllocation.objects.filter(subject_teacher=staff, is_active=True)
        class_stream_ids = set(allocations.values_list("academic_class_stream_id", flat=True))
        class_stream_ids.update(
            staff.academicclassstream_set.values_list("id", flat=True)
            if hasattr(staff, "academicclassstream_set") else []
        )
        student_ids = ClassRegister.objects.filter(
            academic_class_stream_id__in=class_stream_ids
        ).values_list("student_id", flat=True)
        return queryset.filter(pk__in=student_ids)
    return queryset


def _school_context() -> dict[str, Any]:
    school = SchoolSetting.objects.first()
    year = AcademicYear.objects.filter(is_current=True).first() or AcademicYear.objects.order_by("-id").first()
    term = Term.objects.filter(is_current=True).select_related("academic_year").first()
    if term and year and term.academic_year_id != year.id:
        term = Term.objects.filter(academic_year=year).order_by("term").first()
    return {
        "school": {
            "name": getattr(school, "school_name", "Tafiti School") or "Tafiti School",
            "motto": getattr(school, "school_motto", "") or "",
            "logo": _safe_file_url(getattr(school, "school_logo", None)) if school else "",
            "primary_color": getattr(school, "primary_color", "#07543F") or "#07543F",
            "secondary_color": getattr(school, "secondary_color", "#087F5B") or "#087F5B",
            "accent_color": getattr(school, "accent_color", "#D79B35") or "#D79B35",
        },
        "academic_context": {
            "year": _str(getattr(year, "academic_year", "")),
            "term": _str(term) if term else "",
            "year_id": getattr(year, "id", None),
            "term_id": getattr(term, "id", None),
        },
    }


def _navigation_for(request) -> list[dict[str, Any]]:
    allowed = _allowed_resources(request)
    role = canonical_role_label(_active_role(request))
    if role == "Parent":
        family_items = [
            {"slug": "parent-children", "label": "My children", "icon": "users", "resource": "parent-children"},
        ]
        if "attendance" in allowed:
            family_items.append({"slug": "parent-attendance", "label": "Attendance", "icon": "calendar-check", "resource": "parent-attendance"})
        if "fees" in allowed:
            family_items.append({"slug": "parent-finance", "label": "Finance", "icon": "wallet-cards", "resource": "parent-finance"})
        family_items.extend([
            {"slug": "parent-communication", "label": "Communication", "icon": "messages-square", "resource": "parent-communication"},
            {"slug": "parent-calendar", "label": "Calendar", "icon": "calendar-days", "resource": "parent-calendar"},
        ])
        academic_items = []
        if "results" in allowed:
            academic_items.extend([
                {"slug": "parent-results", "label": "Academic", "icon": "chart-no-axes-column", "resource": "parent-results"},
                {"slug": "parent-reports", "label": "Reports", "icon": "file-text", "resource": "parent-reports"},
            ])
        return [
            {"key": "overview", "label": "Overview", "items": [
                {"slug": "overview", "label": "Home", "icon": "layout-dashboard", "resource": None},
            ]},
            {"key": "family", "label": "Family & school", "items": family_items},
            *([{"key": "academics", "label": "Academics", "items": academic_items}] if academic_items else []),
        ]
    groups = []
    for group_key, items in NAVIGATION.items():
        visible = []
        for item in items:
            resource = item["resource"]
            required_roles = item.get("roles")
            if required_roles and role not in required_roles:
                continue
            if resource is None or "*" in allowed or resource in allowed:
                visible.append(item)
        if visible:
            groups.append({"key": group_key, "label": GROUP_LABELS[group_key], "items": visible})
    return groups


def _paginate(request, rows: list[dict[str, Any]], *, default_page_size: int = 25) -> dict[str, Any]:
    try:
        page = max(int(request.query_params.get("page", "1")), 1)
    except ValueError:
        page = 1
    try:
        page_size = min(max(int(request.query_params.get("page_size", str(default_page_size))), 1), 100)
    except ValueError:
        page_size = default_page_size
    total = len(rows)
    pages = max(ceil(total / page_size), 1)
    if page > pages:
        page = pages
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "rows": rows[start:end],
        "pagination": {"page": page, "page_size": page_size, "total": total, "pages": pages},
    }


def _search(rows: list[dict[str, Any]], q: str) -> list[dict[str, Any]]:
    query = q.strip().casefold()
    if not query:
        return rows
    return [
        row for row in rows
        if any(query in _str(value).casefold() for value in row.values() if value is not None)
    ]


def _resource_students(request):
    qs = _scope_students(
        request,
        Student.objects.select_related("current_class", "stream", "term", "academic_year").order_by("student_name"),
    )
    rows = [
        {
            "id": row.id,
            "student_id": row.display_student_id,
            "photo": _safe_file_url(row.photo),
            "name": row.student_name,
            "gender": row.get_gender_display(),
            "class": _str(row.current_class),
            "stream": _str(row.stream),
            "term": _str(row.term),
            "guardian": row.guardian,
            "contact": row.contact,
            "status": "Active" if row.is_active else "Inactive",
        }
        for row in qs[:2000]
    ]
    return {
        "title": "My children" if _is_parent_context(request) else "Students",
        "description": "Student profiles, enrolment placement and guardian information.",
        "columns": [
            ["photo", "Photo"], ["student_id", "Student ID"], ["name", "Student"], ["gender", "Gender"],
            ["class", "Class"], ["stream", "Stream"], ["term", "Term"], ["status", "Status"],
        ],
        "rows": rows,
    }


def _resource_staff(request):
    qs = Staff.objects.prefetch_related("roles").order_by("first_name", "last_name")
    rows = [
        {
            "id": row.id,
            "photo": _safe_file_url(row.staff_photo),
            "name": f"{row.first_name} {row.last_name}".strip(),
            "roles": ", ".join(row.roles.values_list("name", flat=True)) or "—",
            "department": row.department,
            "email": row.email,
            "contact": row.contacts,
            "status": row.staff_status,
        }
        for row in qs[:2000]
    ]
    return {
        "title": "Staff",
        "description": "School staff, responsibilities, departments and account-ready identity details.",
        "columns": [["photo", "Photo"], ["name", "Staff member"], ["roles", "Roles"], ["department", "Department"], ["email", "Email"], ["contact", "Contact"], ["status", "Status"]],
        "rows": rows,
    }


def _resource_admissions(request):
    qs = AdmissionApplication.objects.select_related("applying_class", "preferred_stream").order_by("-created_at")
    rows = [
        {
            "id": row.id,
            "application": row.application_number,
            "student": row.student_name,
            "class": _str(row.applying_class),
            "stream": _str(row.preferred_stream) or "—",
            "guardian": row.guardian,
            "contact": row.contact,
            "status": row.get_status_display(),
            "source": row.get_source_display(),
            "updated": _date(row.updated_at),
        }
        for row in qs[:2000]
    ]
    return {
        "title": "Admissions",
        "description": "Applications from intake through decision and enrolment.",
        "columns": [["application", "Application"], ["student", "Applicant"], ["class", "Applying class"], ["stream", "Preferred stream"], ["guardian", "Guardian"], ["status", "Status"], ["updated", "Updated"]],
        "rows": rows,
    }


def _resource_parents(request):
    qs = ParentAccess.objects.select_related("user", "student").order_by("student__student_name")
    rows = [
        {
            "id": row.id,
            "parent": row.user.get_full_name().strip() or row.user.get_username(),
            "username": row.user.get_username(),
            "student": row.student.student_name,
            "academics": "Allowed" if row.can_view_academics else "Blocked",
            "finance": "Allowed" if row.can_view_finance else "Blocked",
            "attendance": "Allowed" if row.can_view_attendance else "Blocked",
            "status": "Active" if row.is_active and row.is_verified else "Pending / inactive",
        }
        for row in qs[:2000]
    ]
    return {
        "title": "Parent access",
        "description": "Verified parent accounts and the children each account is authorised to view.",
        "columns": [["parent", "Parent"], ["username", "Username"], ["student", "Student"], ["academics", "Academics"], ["finance", "Finance"], ["attendance", "Attendance"], ["status", "Status"]],
        "rows": rows,
    }


def _resource_classes(request):
    qs = AcademicClass.objects.select_related("Class", "section", "academic_year", "term").prefetch_related("class_streams__stream").order_by("-academic_year__academic_year", "Class__name")
    if canonical_role_label(_active_role(request)) in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        if staff:
            qs = qs.filter(Q(class_streams__class_teacher=staff) | Q(class_streams__subjects__subject_teacher=staff)).distinct()
        else:
            qs = qs.none()
    rows = [
        {
            "id": row.id,
            "class": _str(row.Class),
            "section": _str(row.section),
            "year": _str(row.academic_year),
            "term": _str(row.term),
            "streams": ", ".join(stream.stream.stream for stream in row.class_streams.all()) or "—",
            "fees": _money(row.fees_amount),
        }
        for row in qs[:1000]
    ]
    return {
        "title": "Classes & streams",
        "description": "Academic classes, terms, streams and class-level configuration.",
        "columns": [["class", "Class"], ["section", "Section"], ["year", "Academic year"], ["term", "Term"], ["streams", "Streams"], ["fees", "Class fee"]],
        "rows": rows,
    }


def _resource_subjects(request):
    qs = Subject.objects.select_related("section").order_by("section__section_name", "name")
    if canonical_role_label(_active_role(request)) in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        if staff:
            qs = qs.filter(subjects__subject_teacher=staff, subjects__is_active=True).distinct()
        else:
            qs = qs.none()
    rows = [
        {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "section": _str(row.section),
            "type": row.type,
            "credit_hours": row.credit_hours,
        }
        for row in qs[:1000]
    ]
    return {
        "title": "Subjects",
        "description": "Subjects configured for each school section and teaching allocation context.",
        "columns": [["code", "Code"], ["name", "Subject"], ["section", "Section"], ["type", "Type"], ["credit_hours", "Credit hours"]],
        "rows": rows,
    }


def _resource_results(request):
    if request.query_params.get("view") == "verification":
        from .workspace_context import result_verification_queue

        return result_verification_queue(request)

    qs = Result.objects.select_related(
        "student", "assessment__assessment_type", "assessment__subject", "assessment__academic_class__Class",
        "batch",
    ).order_by("-id")
    role = canonical_role_label(_active_role(request))
    if role == "Parent":
        allowed_ids = _parent_accesses(request.user).filter(can_view_academics=True).values_list("student_id", flat=True)
        qs = qs.filter(student_id__in=allowed_ids, status="VERIFIED")
    elif role in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        if staff:
            allocations = ClassSubjectAllocation.objects.filter(subject_teacher=staff, is_active=True)
            pairs = list(allocations.values_list("academic_class_stream__academic_class_id", "subject_id"))
            condition = Q(pk__in=[])
            for class_id, subject_id in pairs:
                condition |= Q(assessment__academic_class_id=class_id, assessment__subject_id=subject_id)
            qs = qs.filter(condition)
        else:
            qs = qs.none()
    rows = [
        {
            "id": row.id,
            "student": row.student.student_name,
            "class": _str(row.assessment.academic_class.Class),
            "subject": row.assessment.subject.name,
            "assessment": row.assessment.assessment_type.name,
            "score": _str(row.score),
            "out_of": row.assessment.out_of,
            "grade": row.grade,
            "status": row.get_status_display(),
        }
        for row in qs[:3000]
    ]
    return {
        "title": "Results",
        "description": "Assessment marks and verification status from the existing results engine.",
        "columns": [["student", "Student"], ["class", "Class"], ["subject", "Subject"], ["assessment", "Assessment"], ["score", "Score"], ["out_of", "Out of"], ["grade", "Grade"], ["status", "Verification"]],
        "rows": rows,
    }


def _resource_attendance(request):
    qs = AttendanceSession.objects.select_related("class_stream", "subject", "teacher", "term", "time_slot").prefetch_related("records").order_by("-date", "-id")
    role = canonical_role_label(_active_role(request))
    if role == "Parent":
        student_ids = _parent_accesses(request.user).filter(can_view_attendance=True).values_list("student_id", flat=True)
        qs = qs.filter(records__student_id__in=student_ids).distinct()
    elif role in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        qs = qs.filter(teacher=staff) if staff else qs.none()
    rows = []
    for row in qs[:1500]:
        counts = row.status_counts()
        rows.append({
            "id": row.id,
            "date": _date(row.date),
            "class": _str(row.class_stream),
            "subject": _str(row.subject),
            "teacher": _str(row.teacher),
            "present": counts.get("present", 0),
            "late": counts.get("late", 0),
            "absent": counts.get("absent", 0),
            "status": "Locked" if row.is_locked else "Open",
        })
    return {
        "title": "Attendance",
        "description": "Lesson attendance sessions, completion state and status counts.",
        "columns": [["date", "Date"], ["class", "Class / stream"], ["subject", "Subject"], ["teacher", "Teacher"], ["present", "Present"], ["late", "Late"], ["absent", "Absent"], ["status", "Session"]],
        "rows": rows,
    }


def _resource_timetable(request):
    qs = Timetable.objects.select_related("class_stream", "subject", "teacher", "time_slot", "classroom").order_by("weekday", "time_slot__start_time")
    if canonical_role_label(_active_role(request)) in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        qs = qs.filter(teacher=staff) if staff else qs.none()
    rows = [
        {
            "id": row.id,
            "day": row.get_weekday_display(),
            "time": _str(row.time_slot),
            "class": _str(row.class_stream),
            "subject": _str(row.subject),
            "teacher": _str(row.teacher) or "—",
            "room": _str(row.classroom) or "—",
        }
        for row in qs[:2000]
    ]
    return {
        "title": "Timetable",
        "description": "Scheduled lessons using the existing allocation and conflict rules.",
        "columns": [["day", "Day"], ["time", "Time"], ["class", "Class / stream"], ["subject", "Subject"], ["teacher", "Teacher"], ["room", "Room"]],
        "rows": rows,
    }


def _resource_fees(request):
    qs = StudentBill.objects.select_related("student", "academic_class__Class", "academic_class__term").prefetch_related("items", "payments", "applied_credits").order_by("-bill_date", "-id")
    if _is_parent_context(request):
        accesses = _parent_accesses(request.user)
        allowed_ids = list(accesses.filter(can_view_finance=True).values_list("student_id", flat=True))
        qs = qs.filter(student_id__in=allowed_ids)
    rows = []
    for row in qs[:2000]:
        balance = Decimal(str(row.balance))
        paid = Decimal(str(row.amount_paid))
        bill_status = "Paid" if balance <= 0 else ("Partial" if paid > 0 else "Outstanding")
        rows.append({
            "id": row.id,
            "student": row.student.student_name,
            "class": _str(row.academic_class.Class),
            "term": _str(row.academic_class.term),
            "bill_date": _date(row.bill_date),
            "due_date": _date(row.due_date),
            "billed": _money(row.total_amount),
            "paid": _money(paid),
            "balance": _money(balance),
            "status": bill_status,
        })
    filters = [
        {"value": "all", "label": "All accounts", "count": len(rows)},
        {"value": "outstanding", "label": "Outstanding", "count": sum(row["status"] == "Outstanding" for row in rows)},
        {"value": "partial", "label": "Partially paid", "count": sum(row["status"] == "Partial" for row in rows)},
        {"value": "paid", "label": "Paid", "count": sum(row["status"] == "Paid" for row in rows)},
    ]
    current_filter = request.query_params.get("status", "all").lower()
    if current_filter not in {"all", "outstanding", "partial", "paid"}:
        current_filter = "all"
    unfiltered_rows = rows
    if current_filter != "all":
        selected_status = {"outstanding": "Outstanding", "partial": "Partial", "paid": "Paid"}[current_filter]
        rows = [row for row in rows if row["status"] == selected_status]
    billed_total = sum((Decimal(row["billed"]) for row in unfiltered_rows), Decimal("0"))
    paid_total = sum((Decimal(row["paid"]) for row in unfiltered_rows), Decimal("0"))
    outstanding_total = sum(
        (max(Decimal("0"), Decimal(row["balance"])) for row in unfiltered_rows),
        Decimal("0"),
    )
    return {
        "title": "Fees & payments",
        "description": "Fee collection overview, student billing accounts and outstanding balances from the live ledger.",
        "metrics": [
            {"label": "Total billed", "value": f"UGX {_money(billed_total)}", "hint": f"{len(unfiltered_rows)} student accounts", "tone": "blue"},
            {"label": "Total collected", "value": f"UGX {_money(paid_total)}", "hint": "Recorded payments", "tone": "green"},
            {"label": "Outstanding", "value": f"UGX {_money(outstanding_total)}", "hint": "Balance due across accounts", "tone": "gold"},
            {"label": "Paid accounts", "value": sum(row["status"] == "Paid" for row in unfiltered_rows), "hint": "Bills settled or in credit", "tone": "violet"},
        ],
        "filters": filters,
        "active_filter": current_filter,
        "columns": [["student", "Student"], ["class", "Class"], ["term", "Term"], ["bill_date", "Bill date"], ["due_date", "Due date"], ["billed", "Billed"], ["paid", "Paid"], ["balance", "Balance"], ["status", "Status"]],
        "rows": rows,
    }


def _resource_fee_payments(request):
    payments = Payment.objects.select_related(
        "bill__student", "bill__academic_class__Class", "bill__academic_class__term",
    ).order_by("-payment_date", "-id")
    if _is_parent_context(request):
        allowed_ids = _parent_accesses(request.user).filter(
            can_view_finance=True,
        ).values_list("student_id", flat=True)
        payments = payments.filter(bill__student_id__in=allowed_ids)

    reconciled_ids = BankTransaction.objects.filter(
        reconciled=True,
        reconciled_with__isnull=False,
    ).values_list("reconciled_with_id", flat=True)
    current_filter = request.query_params.get("status", "all").lower()
    if current_filter == "reconciled":
        qs = payments.filter(pk__in=reconciled_ids)
    elif current_filter == "unreconciled":
        qs = payments.exclude(pk__in=reconciled_ids)
    else:
        current_filter = "all"
        qs = payments

    all_total = payments.count()
    reconciled_total = payments.filter(pk__in=reconciled_ids).count()
    unreconciled = payments.exclude(pk__in=reconciled_ids)
    today = timezone.localdate()
    collected_today = payments.filter(payment_date=today).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    unreconciled_amount = unreconciled.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total_collected = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    payment_rows = list(qs[:3000])
    reconciled_payment_ids = set(
        BankTransaction.objects.filter(
            reconciled=True,
            reconciled_with__isnull=False,
            reconciled_with_id__in=[row.pk for row in payment_rows],
        ).values_list("reconciled_with_id", flat=True)
    )
    rows = [
        {
            "id": row.id,
            "date": _date(row.payment_date),
            "reference": row.reference_no,
            "student": row.bill.student.student_name,
            "class": _str(row.bill.academic_class.Class),
            "term": _str(row.bill.academic_class.term),
            "method": row.payment_method,
            "category": row.fee_category or "—",
            "amount": _money(row.amount),
            "recorded_by": row.recorded_by or "—",
            "reconciliation": "Reconciled" if row.pk in reconciled_payment_ids else "Unreconciled",
        }
        for row in payment_rows
    ]
    return {
        "title": "Fee payments",
        "description": "Review recorded fee payments and the bank reconciliation status linked to each receipt.",
        "metrics": [
            {"label": "Total collected", "value": f"UGX {_money(total_collected)}", "hint": f"{all_total} payment records", "tone": "blue"},
            {"label": "Collected today", "value": f"UGX {_money(collected_today)}", "hint": today.strftime("%d %b %Y"), "tone": "green"},
            {"label": "Unreconciled", "value": f"UGX {_money(unreconciled_amount)}", "hint": f"{all_total - reconciled_total} payments to match", "tone": "gold"},
            {"label": "Reconciled", "value": reconciled_total, "hint": "Matched to a bank transaction", "tone": "violet"},
        ],
        "filters": [
            {"value": "all", "label": "All payments", "count": all_total},
            {"value": "unreconciled", "label": "Unreconciled", "count": all_total - reconciled_total},
            {"value": "reconciled", "label": "Reconciled", "count": reconciled_total},
        ],
        "active_filter": current_filter,
        "columns": [["date", "Date"], ["reference", "Receipt / reference"], ["student", "Student"], ["class", "Class"], ["term", "Term"], ["method", "Method"], ["category", "Category"], ["amount", "Amount (UGX)"], ["reconciliation", "Bank status"], ["recorded_by", "Recorded by"]],
        "rows": rows,
    }


def _resource_fee_class_bills(request):
    qs = ClassBill.objects.select_related(
        "academic_class__Class", "academic_class__academic_year",
        "academic_class__term", "bill_item",
    ).order_by("-academic_class__academic_year__academic_year", "academic_class__Class__name")
    rows = [
        {
            "id": row.id,
            "class": _str(row.academic_class.Class),
            "year": _str(row.academic_class.academic_year),
            "term": _str(row.academic_class.term),
            "item": row.bill_item.item_name,
            "amount": _money(row.amount),
        }
        for row in qs[:2000]
    ]
    return {
        "title": "Class bills",
        "description": "Fee items and amounts configured for each academic class.",
        "columns": [["class", "Class"], ["year", "Academic year"], ["term", "Term"], ["item", "Fee item"], ["amount", "Amount (UGX)"]],
        "rows": rows,
    }


def _resource_fee_items(request):
    rows = [
        {
            "id": row.id,
            "name": row.item_name,
            "category": row.get_category_display(),
            "duration": row.get_bill_duration_display(),
            "description": row.description,
        }
        for row in BillItem.objects.order_by("item_name")[:1000]
    ]
    return {
        "title": "Fee categories",
        "description": "Reusable fee items applied to class and student bills.",
        "columns": [["name", "Fee item"], ["category", "Category"], ["duration", "Billing period"], ["description", "Description"]],
        "rows": rows,
    }


def _resource_finance(request):
    qs = Expenditure.objects.select_related("budget_item__department", "budget_item__expense", "vendor").prefetch_related("items").order_by("-date_incurred", "-id")
    rows = [
        {
            "id": row.id,
            "date": _date(row.date_incurred),
            "department": _str(row.budget_item.department),
            "category": _str(row.budget_item.expense),
            "vendor": _str(row.vendor) or "—",
            "description": row.description,
            "amount": _money(row.amount),
            "approved_by": row.approved_by or "—",
            "status": row.payment_status,
        }
        for row in qs[:2000]
    ]
    return {
        "title": "Finance",
        "description": "Budget-linked expenditure, vendors, approvals and payment state.",
        "columns": [["date", "Date"], ["department", "Department"], ["category", "Category"], ["vendor", "Vendor"], ["description", "Description"], ["amount", "Amount"], ["approved_by", "Approved by"], ["status", "Payment"]],
        "rows": rows,
    }


def _resource_finance_budgets(request):
    qs = Budget.objects.select_related("academic_year", "term").prefetch_related(
        "budget_items__budget_expenditures__items",
    ).order_by("-academic_year__academic_year", "-term__id")
    rows = [
        {
            "id": row.id,
            "year": _str(row.academic_year),
            "term": _str(row.term),
            "status": row.status,
            "allocated": _money(row.budget_total),
        }
        for row in qs[:1000]
    ]
    return {
        "title": "Budgets",
        "description": "Term budgets and their allocated totals.",
        "columns": [["year", "Academic year"], ["term", "Term"], ["status", "Status"], ["allocated", "Allocated (UGX)"]],
        "rows": rows,
    }


def _resource_finance_budget_items(request):
    qs = BudgetItem.objects.select_related(
        "budget__academic_year", "budget__term", "department", "expense",
    ).prefetch_related("budget_expenditures__items").order_by(
        "-budget__academic_year__academic_year", "department__name", "expense__name",
    )
    rows = [
        {
            "id": row.id,
            "year": _str(row.budget.academic_year),
            "term": _str(row.budget.term),
            "department": _str(row.department),
            "expense": _str(row.expense),
            "allocated": _money(row.allocated_amount),
            "spent": _money(row.amount_spent),
            "remaining": _money(row.remaining_amount),
        }
        for row in qs[:2000]
    ]
    return {
        "title": "Budget allocations",
        "description": "Department and expense allocations with live spend and remaining balances.",
        "columns": [["year", "Academic year"], ["term", "Term"], ["department", "Department"], ["expense", "Expense"], ["allocated", "Allocated (UGX)"], ["spent", "Spent (UGX)"], ["remaining", "Remaining (UGX)"]],
        "rows": rows,
    }


def _resource_finance_expenditure_items(request):
    qs = ExpenditureItem.objects.select_related(
        "expenditure__budget_item__department", "expenditure__vendor",
    ).order_by("-expenditure__date_incurred", "item_name")
    rows = [
        {
            "id": row.id,
            "date": _date(row.expenditure.date_incurred),
            "expenditure": row.expenditure.description,
            "department": _str(row.expenditure.budget_item.department),
            "item": row.item_name,
            "quantity": _str(row.quantity),
            "units": row.get_units_display(),
            "unit_cost": _money(row.unit_cost),
            "amount": _money(row.amount),
        }
        for row in qs[:3000]
    ]
    return {
        "title": "Expenditure items",
        "description": "Itemized costs contributing to recorded expenditure totals.",
        "columns": [["date", "Date"], ["expenditure", "Expenditure"], ["department", "Department"], ["item", "Item"], ["quantity", "Quantity"], ["units", "Units"], ["unit_cost", "Unit cost (UGX)"], ["amount", "Amount (UGX)"]],
        "rows": rows,
    }


def _resource_finance_expenses(request):
    rows = [
        {"id": row.id, "name": row.name, "description": row.description or "—"}
        for row in Expense.objects.order_by("name")[:1000]
    ]
    return {
        "title": "Expense categories",
        "description": "Expense types used by budget lines and expenditure records.",
        "columns": [["name", "Expense"], ["description", "Description"]],
        "rows": rows,
    }


def _resource_finance_vendors(request):
    rows = [
        {"id": row.id, "name": row.name, "contact": row.contact, "email": row.email or "—", "address": row.address}
        for row in Vendor.objects.order_by("name")[:1000]
    ]
    return {
        "title": "Vendors",
        "description": "Supplier records referenced by school expenditure.",
        "columns": [["name", "Vendor"], ["contact", "Contact"], ["email", "Email"], ["address", "Address"]],
        "rows": rows,
    }


def _resource_finance_income(request):
    rows = [
        {"id": row.id, "name": row.name, "description": row.description or "—"}
        for row in IncomeSource.objects.order_by("name")[:1000]
    ]
    return {
        "title": "Income sources",
        "description": "Income categories available to finance transactions.",
        "columns": [["name", "Income source"], ["description", "Description"]],
        "rows": rows,
    }


def _resource_library(request):
    qs = LibraryLoan.objects.select_related("copy__book", "student", "staff").order_by("-issued_at")
    rows = [
        {
            "id": row.id,
            "accession": row.copy.accession_number,
            "book": row.copy.book.title,
            "borrower": _str(row.borrower),
            "borrower_type": "Student" if row.student_id else "Staff",
            "issued": _date(row.issued_at),
            "due": _date(row.due_at),
            "returned": _date(row.returned_at) or "—",
            "status": "Overdue" if row.is_overdue else ("Returned" if row.returned_at else "On loan"),
        }
        for row in qs[:2000]
    ]
    return {
        "title": "Library",
        "description": "Current and historical circulation across the physical library collection.",
        "columns": [["accession", "Accession"], ["book", "Book"], ["borrower", "Borrower"], ["borrower_type", "Type"], ["issued", "Issued"], ["due", "Due"], ["returned", "Returned"], ["status", "Status"]],
        "rows": rows,
    }


def _resource_communication(request):
    role = canonical_role_label(_active_role(request))
    now = timezone.now()
    announcements = Announcement.objects.filter(is_active=True).order_by("-starts_at")
    events = Event.objects.filter(is_active=True).order_by("-start_datetime")
    if role == "Parent":
        announcements = announcements.filter(
            audience__in=["all", "parents"],
            starts_at__lte=now,
        ).filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        events = events.filter(audience__in=["all", "parents"])
    rows = []
    for row in announcements[:500]:
        rows.append({
            "id": f"announcement-{row.id}", "type": "Announcement", "title": row.title,
            "audience": row.get_audience_display(), "when": _date(row.starts_at),
            "priority": row.get_priority_display(), "status": "Active",
        })
    for row in events[:500]:
        rows.append({
            "id": f"event-{row.id}", "type": "Event", "title": row.title,
            "audience": row.get_audience_display(), "when": _date(row.start_datetime),
            "priority": row.location or "—", "status": "Active",
        })
    rows.sort(key=lambda item: item["when"], reverse=True)
    return {
        "title": "Communication",
        "description": "Announcements and events visible to the current workspace.",
        "columns": [["type", "Type"], ["title", "Title"], ["audience", "Audience"], ["when", "Date"], ["priority", "Priority / location"], ["status", "Status"]],
        "rows": rows,
    }


def _resource_audit(request):
    qs = AuditLog.objects.select_related("user", "content_type").order_by("-timestamp")
    rows = [
        {
            "id": row.id,
            "time": _date(row.timestamp),
            "user": row.username or (_str(row.user) if row.user_id else "System"),
            "action": row.get_action_display(),
            "object": row.object_repr or "—",
            "method": row.method or "—",
            "path": row.path or "—",
        }
        for row in qs[:2500]
    ]
    return {
        "title": "Audit trail",
        "description": "Security and data-change history captured by the existing audit subsystem.",
        "columns": [["time", "Time"], ["user", "User"], ["action", "Action"], ["object", "Object"], ["method", "Method"], ["path", "Path"]],
        "rows": rows,
    }


def _resource_settings(request):
    school = SchoolSetting.objects.first()
    rows = []
    if school:
        rows.append({
            "id": school.id,
            "school": school.school_name,
            "motto": school.school_motto,
            "email": school.email,
            "mobile": school.mobile,
            "city": school.city,
            "country": school.country,
            "levels": ", ".join([
                label for enabled, label in [
                    (school.offers_primary, "Primary"),
                    (school.offers_secondary_lower, "O-Level"),
                    (school.offers_secondary_upper, "A-Level"),
                ] if enabled
            ]) or "Not configured",
        })
    return {
        "title": "School settings",
        "description": "Core identity and education-level configuration. Editing will be migrated as a dedicated form.",
        "columns": [["school", "School"], ["motto", "Motto"], ["email", "Email"], ["mobile", "Mobile"], ["city", "City"], ["country", "Country"], ["levels", "Education levels"]],
        "rows": rows,
    }


RESOURCE_BUILDERS: dict[str, Callable] = {
    "students": _resource_students,
    "staff": _resource_staff,
    "admissions": _resource_admissions,
    "parents": _resource_parents,
    "classes": _resource_classes,
    "subjects": _resource_subjects,
    "results": _resource_results,
    "attendance": _resource_attendance,
    "timetable": _resource_timetable,
    "fees": _resource_fees,
    "fees-payments": _resource_fee_payments,
    "fees-class-bills": _resource_fee_class_bills,
    "fees-bill-items": _resource_fee_items,
    "finance": _resource_finance,
    "finance-budgets": _resource_finance_budgets,
    "finance-budget-items": _resource_finance_budget_items,
    "finance-expenditure-items": _resource_finance_expenditure_items,
    "finance-expenses": _resource_finance_expenses,
    "finance-vendors": _resource_finance_vendors,
    "finance-income": _resource_finance_income,
    "library": _resource_library,
    "communication": _resource_communication,
    "audit": _resource_audit,
    "settings": _resource_settings,
}


def _dashboard_stats(request) -> list[dict[str, Any]]:
    role = canonical_role_label(_active_role(request))
    student_qs = _scope_students(request, Student.objects.all())

    if role == "Parent":
        student_ids = _parent_accesses(request.user).filter(can_view_finance=True).values_list("student_id", flat=True)
        bills = StudentBill.objects.filter(student_id__in=student_ids).prefetch_related("items", "payments", "applied_credits")
        balance = sum((bill.balance for bill in bills), Decimal("0"))
        attendance_student_ids = _parent_accesses(request.user).filter(
            can_view_attendance=True,
        ).values_list("student_id", flat=True)
        attendance = AttendanceSession.objects.filter(records__student_id__in=attendance_student_ids).distinct().count()
        parent_student_ids = _parent_accesses(request.user).values_list("student_id", flat=True)
        unread_notices = ParentNotification.objects.filter(
            user=request.user,
            read_at__isnull=True,
        ).filter(Q(student__isnull=True) | Q(student_id__in=parent_student_ids)).count()
        return [
            {"label": "Children", "value": student_qs.count(), "hint": "Linked to this account", "tone": "green"},
            {"label": "Outstanding fees", "value": _money(balance), "hint": "Across linked children", "tone": "gold", "currency": True},
            {"label": "Attendance sessions", "value": attendance, "hint": "Recorded sessions", "tone": "blue"},
            {"label": "Unread notices", "value": unread_notices, "hint": "Parent notifications", "tone": "violet"},
        ]

    if role == "Bursar":
        bills = StudentBill.objects.prefetch_related("items", "payments", "applied_credits")
        outstanding = sum((bill.balance for bill in bills), Decimal("0"))
        today = timezone.localdate()
        payments = Payment.objects.aggregate(total=Sum("amount"))["total"] or 0
        today_collections = Payment.objects.filter(payment_date=today).aggregate(total=Sum("amount"))["total"] or 0
        unreconciled = BankTransaction.objects.filter(
            transaction_type="Credit",
            reconciled=False,
        ).count()
        credits = StudentCredit.objects.filter(is_applied=False).aggregate(total=Sum("amount"))["total"] or 0
        return [
            {"label": "Collections today", "value": _money(today_collections), "hint": f"Payments on {today:%d %b}", "tone": "green", "currency": True},
            {"label": "Total collected", "value": _money(payments), "hint": "Recorded fee payments", "tone": "blue", "currency": True},
            {"label": "Outstanding fees", "value": _money(outstanding), "hint": "Current ledger balance", "tone": "gold", "currency": True},
            {"label": "Pending reconciliation", "value": unreconciled, "hint": "Unmatched bank credits", "tone": "violet"},
            {"label": "Student credits", "value": _money(credits), "hint": "Available, unapplied credits", "tone": "green", "currency": True},
        ]

    if role in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        allocations = ClassSubjectAllocation.objects.filter(subject_teacher=staff, is_active=True) if staff else ClassSubjectAllocation.objects.none()
        pending = ResultBatch.objects.filter(assessment__subject_id__in=allocations.values_list("subject_id", flat=True), status__in=["DRAFT", "PENDING"]).distinct().count()
        teacher_sessions = AttendanceSession.objects.filter(teacher=staff) if staff else AttendanceSession.objects.none()
        marked_records = AttendanceRecord.objects.filter(session__in=teacher_sessions).exclude(status="unmarked")
        present_records = marked_records.filter(status__in=("present", "late", "excused")).count()
        marked_count = marked_records.count()
        attendance_rate = round(present_records * 100 / marked_count) if marked_count else 0
        return [
            {"label": "My students", "value": student_qs.count(), "hint": "Across assigned classes", "tone": "green"},
            {"label": "My classes", "value": allocations.values("academic_class_id").distinct().count(), "hint": "Assigned class groups", "tone": "blue"},
            {"label": "Attendance rate", "value": f"{attendance_rate}%", "hint": "Across marked sessions", "tone": "violet"},
            {"label": "Pending marks", "value": pending, "hint": "Draft or awaiting verification", "tone": "gold"},
        ]

    if role in {"Librarian", "Library Assistant"}:
        overdue = LibraryLoan.objects.filter(
            returned_at__isnull=True,
            due_at__lt=timezone.now(),
        ).count()
        outstanding_fines = LibraryFine.objects.filter(status=LibraryFine.STATUS_OUTSTANDING).aggregate(
            total=Sum("amount"),
        )["total"] or Decimal("0")
        return [
            {"label": "Book titles", "value": LibraryBook.objects.count(), "hint": "Catalogue titles", "tone": "green"},
            {"label": "Available copies", "value": LibraryCopy.objects.filter(status="available").count(), "hint": "Ready to issue", "tone": "blue"},
            {"label": "Active loans", "value": LibraryLoan.objects.filter(returned_at__isnull=True).count(), "hint": "Currently borrowed", "tone": "gold"},
            {"label": "Overdue loans", "value": overdue, "hint": "Past the return date", "tone": "violet"},
            {"label": "Outstanding fines", "value": _money(outstanding_fines), "hint": "Fines awaiting resolution", "tone": "gold", "currency": True},
        ]

    if role == "Admissions Officer":
        applications = AdmissionApplication.objects.all()
        return [
            {"label": "New applications", "value": applications.filter(status="submitted").count(), "hint": "Ready for initial review", "tone": "blue"},
            {"label": "Under review", "value": applications.filter(status__in=("review", "shortlisted", "assessment", "interview", "waitlisted")).count(), "hint": "Moving through the pipeline", "tone": "gold"},
            {"label": "Approved", "value": applications.filter(status="accepted").count(), "hint": "Awaiting enrolment", "tone": "green"},
            {"label": "Enrolled", "value": applications.filter(status="enrolled").count(), "hint": "Converted to students", "tone": "violet"},
            {"label": "Rejected", "value": applications.filter(status="rejected").count(), "hint": "Closed applications", "tone": "gold"},
        ]

    if role in {"Admin", "Head Teacher"}:
        marked_records = AttendanceRecord.objects.exclude(status="unmarked")
        marked_count = marked_records.count()
        attended_count = marked_records.filter(status__in=("present", "late", "excused")).count()
        attendance_rate = round(attended_count * 100 / marked_count) if marked_count else 0
        fees_collected = Payment.objects.aggregate(total=Sum("amount"))["total"] or 0
        return [
            {"label": "Total students", "value": Student.objects.filter(is_active=True).count(), "hint": "Active student register", "tone": "green"},
            {"label": "Total staff", "value": Staff.objects.filter(staff_status="Active").count(), "hint": "Active staff accounts", "tone": "blue"},
            {"label": "Attendance rate", "value": f"{attendance_rate}%", "hint": "Across marked attendance records", "tone": "violet"},
            {"label": "Fees collected", "value": _money(fees_collected), "hint": "Recorded fee payments", "tone": "green", "currency": True},
            {"label": "Pending results", "value": ResultBatch.objects.filter(status="PENDING").count(), "hint": "Submitted batches to verify", "tone": "gold"},
            {"label": "Admissions", "value": AdmissionApplication.objects.exclude(status__in=["enrolled", "rejected", "withdrawn"]).count(), "hint": "Applications in progress", "tone": "violet"},
        ]

    # Director of Studies and fallback staff summary.
    return [
        {"label": "Active students", "value": Student.objects.filter(is_active=True).count(), "hint": "Current student register", "tone": "green"},
        {"label": "Active staff", "value": Staff.objects.filter(staff_status="Active").count(), "hint": "Staff currently active", "tone": "blue"},
        {"label": "Pending admissions", "value": AdmissionApplication.objects.exclude(status__in=["enrolled", "rejected"]).count(), "hint": "Needs attention", "tone": "gold"},
        {"label": "Results awaiting verification", "value": ResultBatch.objects.filter(status="PENDING").count(), "hint": "Submitted batches", "tone": "violet"},
    ]


def _dashboard_analytics(request) -> dict[str, list[dict[str, Any]]]:
    role = canonical_role_label(_active_role(request))
    analytics: dict[str, list[dict[str, Any]]] = {}
    today = timezone.localdate()

    if role in {"Admin", "Head Teacher", "Director of Studies", "Teacher", "Class Teacher"}:
        attendance = AttendanceRecord.objects.filter(
            session__date__gte=today - timedelta(days=6),
            session__date__lte=today,
        ).exclude(status="unmarked")
        if role in {"Teacher", "Class Teacher"}:
            staff = _staff_for_user(request.user)
            attendance = attendance.filter(session__teacher=staff) if staff else attendance.none()
        daily_attendance = attendance.values("session__date").annotate(
            total=Count("id"),
            present=Count("id", filter=Q(status__in=("present", "late", "excused"))),
        )
        attendance_by_date = {row["session__date"]: row for row in daily_attendance}
        analytics["attendance_trend"] = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            row = attendance_by_date.get(day, {})
            total = row.get("total", 0)
            present = row.get("present", 0)
            analytics["attendance_trend"].append({
                "label": day.strftime("%a"),
                "value": round(present * 100 / total, 1) if total else 0,
                "detail": f"{present} of {total} marked",
            })

    if role in {"Admin", "Head Teacher", "Bursar"}:
        first_month_index = today.year * 12 + today.month - 1 - 5
        start_date = date(first_month_index // 12, first_month_index % 12 + 1, 1)
        monthly_payments = Payment.objects.filter(payment_date__gte=start_date).annotate(
            month=TruncMonth("payment_date"),
        ).values("month").annotate(total=Sum("amount"))
        collections_by_month = {
            row["month"].strftime("%Y-%m"): row["total"] or Decimal("0")
            for row in monthly_payments
        }
        analytics["collection_trend"] = []
        for offset in range(5, -1, -1):
            month_index = today.year * 12 + today.month - 1 - offset
            year, month = divmod(month_index, 12)
            month += 1
            month_key = f"{year:04d}-{month:02d}"
            analytics["collection_trend"].append({
                "label": date(year, month, 1).strftime("%b"),
                "value": float(collections_by_month.get(month_key, Decimal("0"))),
            })
    return analytics


def _parent_dashboard_content(request) -> dict[str, Any]:
    from django.db.models import Q

    from app.services.parent_experience import current_academic_term

    accesses = list(_parent_accesses(request.user).filter(student__is_active=True).select_related(
        "student__current_class", "student__stream",
    ))
    term = current_academic_term()
    children = []
    recent_results = []
    for access in accesses:
        student = access.student
        child = {
            "id": student.pk,
            "name": student.student_name,
            "student_id": student.display_student_id,
            "photo": _safe_file_url(student.photo),
            "class": _str(student.current_class),
            "stream": _str(student.stream),
            "attendance_percent": None,
            "academic_average": None,
            "outstanding_balance": None,
        }
        if access.can_view_attendance:
            attendance = AttendanceRecord.objects.filter(
                student=student,
                session__is_locked=True,
                session__term=term,
            ).exclude(status="unmarked")
            attended = attendance.count()
            present = attendance.filter(status__in=("present", "late")).count()
            child["attendance_percent"] = round(present * 100 / attended, 1) if attended else None
        if access.can_view_academics:
            results = list(Result.objects.filter(
                student=student,
                status="VERIFIED",
                assessment__out_of__gt=0,
                **({"assessment__academic_class__term": term} if term else {}),
            ).select_related("assessment__subject", "assessment__assessment_type").order_by(
                "-assessment__date", "-id",
            ))
            percentages = [
                Decimal(result.score) * Decimal("100") / Decimal(result.assessment.out_of)
                for result in results
            ]
            if percentages:
                child["academic_average"] = round(float(sum(percentages) / len(percentages)), 1)
            for result in results[:5]:
                recent_results.append({
                    "id": result.pk,
                    "student": student.student_name,
                    "student_id": student.pk,
                    "subject": result.assessment.subject.name,
                    "assessment": result.assessment.assessment_type.name,
                    "score": _money(result.score),
                    "out_of": result.assessment.out_of,
                    "percentage": round(float(Decimal(result.score) * Decimal("100") / Decimal(result.assessment.out_of)), 1),
                    "grade": result.grade,
                    "date": _date(result.assessment.date),
                })
        if access.can_view_finance:
            bills = StudentBill.objects.filter(student=student).prefetch_related(
                "items", "payments", "applied_credits",
            )
            child["outstanding_balance"] = _money(sum(
                (Decimal(str(bill.balance)) for bill in bills),
                Decimal("0"),
            ))
        children.append(child)

    now = timezone.now()
    events = Event.objects.filter(
        is_active=True,
        audience__in=("all", "parents"),
        start_datetime__gte=now,
    ).order_by("start_datetime")[:5]
    announcements = Announcement.objects.filter(
        is_active=True,
        audience__in=("all", "parents"),
        starts_at__lte=now,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now)).order_by("-starts_at")[:5]
    recent_results.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
    return {
        "children": children,
        "recent_results": recent_results[:8],
        "upcoming_events": [
            {
                "id": event.pk,
                "title": event.title,
                "starts_at": _date(event.start_datetime),
                "location": event.location,
            }
            for event in events
        ],
        "announcements": [
            {
                "id": announcement.pk,
                "title": announcement.title,
                "body": announcement.body[:260],
                "starts_at": _date(announcement.starts_at),
                "priority": announcement.get_priority_display(),
            }
            for announcement in announcements
        ],
    }


def _attention_items(request) -> list[dict[str, Any]]:
    role = canonical_role_label(_active_role(request))
    items = []
    if role in {"Admin", "Head Teacher", "Director of Studies"}:
        pending = ResultBatch.objects.filter(status="PENDING").count()
        if pending:
            items.append({
                "title": f"{pending} result batch{'es' if pending != 1 else ''} awaiting verification",
                "resource": "results?view=verification&status=PENDING",
                "severity": "warning",
            })
    if role in {"Admin", "Head Teacher", "Admissions Officer", "Director of Studies"}:
        pending_admissions = AdmissionApplication.objects.exclude(status__in=["enrolled", "rejected"]).count()
        if pending_admissions:
            items.append({"title": f"{pending_admissions} admission application{'s' if pending_admissions != 1 else ''} in progress", "resource": "admissions", "severity": "info"})
    if role in {"Admin", "Head Teacher", "Librarian", "Library Assistant"}:
        overdue = sum(1 for loan in LibraryLoan.objects.filter(returned_at__isnull=True).select_related("copy")[:5000] if loan.is_overdue)
        if overdue:
            items.append({"title": f"{overdue} library loan{'s' if overdue != 1 else ''} overdue", "resource": "library", "severity": "warning"})
    return items[:6]


def _notifications(request) -> list[dict[str, Any]]:
    role = canonical_role_label(_active_role(request))
    notices = []
    for row in ResultVerificationNotification.objects.filter(recipient=request.user).order_by("-created_at")[:8]:
        notices.append({
            "id": f"verification-{row.id}", "title": row.title, "message": row.message,
            "created_at": _date(row.created_at), "read": row.read, "kind": "results",
        })
    parent_notices = ParentNotification.objects.filter(user=request.user)
    if role == "Parent":
        parent_student_ids = _parent_accesses(request.user).values_list("student_id", flat=True)
        parent_notices = parent_notices.filter(
            Q(student__isnull=True) | Q(student_id__in=parent_student_ids),
        )
    for row in parent_notices.order_by("-created_at")[:8]:
        notices.append({
            "id": f"parent-{row.id}", "title": row.title, "message": row.message,
            "created_at": _date(row.created_at), "read": bool(row.read_at), "kind": row.kind,
        })
    notices.sort(key=lambda item: item["created_at"], reverse=True)
    return notices[:10]


class WorkspaceBaseAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]


class WorkspaceBootstrapAPIView(WorkspaceBaseAPIView):
    def get(self, request):
        context = _school_context()
        user_context = serialize_user_context(request.user, preferred_context=_token_context(request))
        if canonical_role_label(_active_role(request)) == "Parent":
            from app.services.parent_portal import sync_parent_notifications

            sync_parent_notifications(request.user)
        notifications = _notifications(request)
        return Response({
            **context,
            "user": user_context,
            "navigation": _navigation_for(request),
            "notification_count": sum(1 for item in notifications if not item["read"]),
            "notifications": notifications,
            "migration": {
                "mode": "nextjs_workspace",
                "source_of_truth": "app models",
                "legacy_templates_still_available": True,
            },
        })


class WorkspaceDashboardAPIView(WorkspaceBaseAPIView):
    def get(self, request):
        context = _school_context()
        role = canonical_role_label(_active_role(request))
        if role == "Parent":
            from app.services.parent_portal import sync_parent_notifications

            sync_parent_notifications(request.user)
        return Response({
            **context,
            "role": role,
            "stats": _dashboard_stats(request),
            "analytics": _dashboard_analytics(request),
            "attention": _attention_items(request),
            "notifications": _notifications(request),
            **({"parent_portal": _parent_dashboard_content(request)} if role == "Parent" else {}),
        })


class WorkspaceSearchAPIView(WorkspaceBaseAPIView):
    def get(self, request):
        from .workspace_context import _entity_path, _module_path

        query = request.query_params.get("q", "").strip()
        if len(query) < 2:
            return Response({"results": []})

        results = []
        if _can_access(request, "students"):
            students = _scope_students(
                request,
                Student.objects.select_related("current_class", "stream").filter(
                    Q(student_name__icontains=query) | Q(reg_no__icontains=query) | Q(guardian__icontains=query)
                ),
            ).order_by("student_name")[:6]
            results.extend({
                "kind": "Student", "label": row.student_name,
                "description": f"{row.display_student_id} · {row.current_class} {row.stream}",
                "href": _entity_path(request, "students", row.pk), "icon": "users",
            } for row in students)

        if _can_access(request, "staff"):
            staff_rows = Staff.objects.filter(
                Q(first_name__icontains=query) | Q(last_name__icontains=query) |
                Q(email__icontains=query) | Q(contacts__icontains=query)
            ).order_by("first_name", "last_name")[:5]
            results.extend({
                "kind": "Staff", "label": _str(row),
                "description": f"{row.get_department_display()} · {row.staff_status}",
                "href": _entity_path(request, "staff", row.pk), "icon": "badge-check",
            } for row in staff_rows)

        if _can_access(request, "admissions"):
            applications = AdmissionApplication.objects.select_related("applying_class").filter(
                Q(student_name__icontains=query) | Q(application_number__icontains=query) |
                Q(guardian__icontains=query)
            ).order_by("-updated_at")[:5]
            results.extend({
                "kind": "Admission", "label": row.student_name,
                "description": f"{row.application_number} · {row.get_status_display()}",
                "href": _entity_path(request, "admissions", row.pk), "icon": "user-plus",
            } for row in applications)

        if _can_access(request, "classes"):
            classes = AcademicClass.objects.select_related("Class", "academic_year", "term")
            if canonical_role_label(_active_role(request)) in {"Teacher", "Class Teacher"}:
                staff = _staff_for_user(request.user)
                classes = classes.filter(
                    Q(class_streams__class_teacher=staff) | Q(class_streams__subjects__subject_teacher=staff)
                ).distinct() if staff else classes.none()
            classes = classes.filter(
                Q(Class__name__icontains=query) | Q(Class__code__icontains=query)
            ).order_by("-academic_year__academic_year", "Class__name")[:5]
            results.extend({
                "kind": "Class", "label": _str(row.Class),
                "description": f"{row.academic_year} · {row.term}",
                "href": _entity_path(request, "classes", row.pk), "icon": "school",
            } for row in classes)

        if _can_access(request, "subjects"):
            subjects = Subject.objects.select_related("section")
            if canonical_role_label(_active_role(request)) in {"Teacher", "Class Teacher"}:
                staff = _staff_for_user(request.user)
                subjects = subjects.filter(subjects__subject_teacher=staff, subjects__is_active=True).distinct() if staff else subjects.none()
            subjects = subjects.filter(
                Q(name__icontains=query) | Q(code__icontains=query)
            ).order_by("name")[:5]
            results.extend({
                "kind": "Subject", "label": row.name,
                "description": f"{row.code} · {row.section}",
                "href": _entity_path(request, "subjects", row.pk), "icon": "book-open",
            } for row in subjects)

        if _can_access(request, "fees"):
            bills = StudentBill.objects.select_related("student", "academic_class__Class")
            if _is_parent_context(request):
                allowed_ids = _parent_accesses(request.user).filter(can_view_finance=True).values_list("student_id", flat=True)
                bills = bills.filter(student_id__in=allowed_ids)
            bills = bills.filter(
                Q(student__student_name__icontains=query) | Q(student__reg_no__icontains=query) |
                Q(payments__reference_no__icontains=query)
            ).distinct().order_by("student__student_name")[:5]
            results.extend({
                "kind": "Fee account", "label": row.student.student_name,
                "description": f"Bill #{row.pk} · Balance UGX {_money(row.balance)}",
                "href": _entity_path(request, "fees", row.pk), "icon": "wallet-cards",
            } for row in bills)

        if _can_access(request, "library"):
            books = LibraryBook.objects.filter(
                Q(title__icontains=query) | Q(isbn__icontains=query) | Q(author__icontains=query)
            ).order_by("title")[:5]
            results.extend({
                "kind": "Library book", "label": row.title,
                "description": f"{row.author or 'Unknown author'} · {row.isbn or 'No ISBN'}",
                "href": _module_path(request, "library", query={"q": row.title}), "icon": "library",
            } for row in books)

        return Response({"results": results[:30]})


class WorkspaceResourceAPIView(WorkspaceBaseAPIView):
    def get(self, request, resource: str):
        builder = RESOURCE_BUILDERS.get(resource)
        if not builder:
            return Response({"detail": "Unknown workspace resource."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access(request, resource):
            record_finance_access_denial(request, resource, operation="list")
            return Response(
                {"code": "resource_forbidden", "detail": "Your current role does not have access to this workspace module."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from .workspace_forms import resource_action_policy

        try:
            payload = builder(request)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        rows = _search(payload.pop("rows"), request.query_params.get("q", ""))
        page = _paginate(request, rows)
        return Response({
            "resource": resource,
            **payload,
            "columns": [{"key": key, "label": label} for key, label in payload["columns"]],
            "actions": resource_action_policy(request, resource),
            **page,
        })


class WorkspaceEntityAPIView(WorkspaceBaseAPIView):
    def get(self, request, resource: str, pk: int):
        from django.core.exceptions import ObjectDoesNotExist
        from .workspace_context import build_entity_workspace

        if not _can_access(request, resource):
            record_finance_access_denial(request, resource, operation="view")
            return Response(
                {"detail": "Your current role does not have access to this workspace module."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            payload = build_entity_workspace(request, resource, pk)
        except KeyError:
            return Response({"detail": "This module does not provide a contextual workspace yet."}, status=status.HTTP_404_NOT_FOUND)
        except ObjectDoesNotExist:
            return Response({"detail": "The requested record was not found."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(payload)


class WorkspaceEntityActionAPIView(WorkspaceBaseAPIView):
    def post(self, request, resource: str, pk: int):
        from .workspace_context import perform_entity_action

        if not _can_access(request, resource):
            record_finance_access_denial(request, resource, operation="action")
            return Response(
                {"detail": "Your current role does not have access to this workspace module."},
                status=status.HTTP_403_FORBIDDEN,
            )
        payload, response_status = perform_entity_action(request, resource, pk)
        return Response(payload, status=response_status)


class WorkspaceResourceFormAPIView(WorkspaceBaseAPIView):
    def _check(self, request, resource: str, action: str):
        from .workspace_forms import RESOURCE_FORMS, resource_action_policy

        if resource not in RESOURCE_FORMS:
            return Response({"detail": "This module does not use the standard workspace form yet."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access(request, resource):
            record_finance_access_denial(request, resource, operation=action)
            return Response({"detail": "Your current role cannot access this module."}, status=status.HTTP_403_FORBIDDEN)
        policy = resource_action_policy(request, resource)
        if not policy.get(action, False):
            return Response({"detail": f"Your current role cannot {action} records in this module."}, status=status.HTTP_403_FORBIDDEN)
        return None

    def get(self, request, resource: str, pk: int | None = None):
        from django.core.exceptions import ObjectDoesNotExist
        from .workspace_forms import get_resource_instance, resource_action_policy, serialize_form

        action = "edit" if pk is not None else "create"
        denied = self._check(request, resource, action)
        if denied:
            return denied
        try:
            instance = get_resource_instance(request, resource, pk) if pk is not None else None
        except ObjectDoesNotExist:
            return Response({"detail": "Record not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({**serialize_form(request, resource, instance=instance), "actions": resource_action_policy(request, resource)})

    def post(self, request, resource: str, pk: int | None = None):
        from .workspace_forms import save_resource_form

        if pk is not None:
            return Response({"detail": "Use PATCH to edit an existing record."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        denied = self._check(request, resource, "create")
        if denied:
            return denied
        instance, errors = save_resource_form(request, resource, request.data, files=request.FILES)
        if errors:
            return Response({"detail": "Please correct the highlighted fields.", "errors": errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Record created successfully.", "id": getattr(instance, "pk", None)}, status=status.HTTP_201_CREATED)

    def patch(self, request, resource: str, pk: int | None = None):
        from django.core.exceptions import ObjectDoesNotExist
        from .workspace_forms import get_resource_instance, save_resource_form

        if pk is None:
            return Response({"detail": "A record id is required."}, status=status.HTTP_400_BAD_REQUEST)
        denied = self._check(request, resource, "edit")
        if denied:
            return denied
        try:
            instance = get_resource_instance(request, resource, pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Record not found."}, status=status.HTTP_404_NOT_FOUND)
        saved, errors = save_resource_form(request, resource, request.data, instance=instance, files=request.FILES)
        if errors:
            return Response({"detail": "Please correct the highlighted fields.", "errors": errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Changes saved successfully.", "id": getattr(saved, "pk", pk)})

    def delete(self, request, resource: str, pk: int | None = None):
        from django.core.exceptions import ObjectDoesNotExist
        from .workspace_forms import delete_resource, get_resource_instance

        if pk is None:
            return Response({"detail": "A record id is required."}, status=status.HTTP_400_BAD_REQUEST)
        denied = self._check(request, resource, "delete")
        if denied:
            return denied
        try:
            instance = get_resource_instance(request, resource, pk)
        except ObjectDoesNotExist:
            return Response({"detail": "Record not found."}, status=status.HTTP_404_NOT_FOUND)
        result = delete_resource(request, resource, instance)
        if result.get("error"):
            return Response({"detail": result["error"]}, status=status.HTTP_409_CONFLICT)
        return Response(result)
