from __future__ import annotations

from decimal import Decimal
from math import ceil
from typing import Any, Callable

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
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
    AttendanceSession,
    AuditLog,
    Budget,
    ClassRegister,
    ClassSubjectAllocation,
    Event,
    Expenditure,
    LibraryBook,
    LibraryCopy,
    LibraryFine,
    LibraryLoan,
    ParentAccess,
    ParentNotification,
    Payment,
    Result,
    ResultBatch,
    ResultVerificationNotification,
    SchoolSetting,
    Staff,
    Student,
    StudentBill,
    Subject,
    Term,
    Timetable,
)

from .auth import assigned_role_labels, canonical_role_label, resolve_active_role, serialize_user_context


# The navigation is deliberately generated server-side.  Hiding a link in the
# browser is not authorization; the same registry is used to reject API calls.
NAVIGATION = {
    "overview": [
        {"slug": "overview", "label": "Overview", "icon": "layout-dashboard", "resource": None},
    ],
    "people": [
        {"slug": "students", "label": "Students", "icon": "users", "resource": "students"},
        {"slug": "staff", "label": "Staff", "icon": "badge-check", "resource": "staff"},
        {"slug": "admissions", "label": "Admissions", "icon": "user-plus", "resource": "admissions"},
        {"slug": "parents", "label": "Parent access", "icon": "contact", "resource": "parents"},
    ],
    "academics": [
        {"slug": "classes", "label": "Classes & streams", "icon": "school", "resource": "classes"},
        {"slug": "subjects", "label": "Subjects", "icon": "book-open", "resource": "subjects"},
        {"slug": "results", "label": "Results", "icon": "chart-no-axes-column", "resource": "results"},
        {"slug": "attendance", "label": "Attendance", "icon": "calendar-check", "resource": "attendance"},
        {"slug": "timetable", "label": "Timetable", "icon": "calendar-days", "resource": "timetable"},
    ],
    "finance": [
        {"slug": "fees", "label": "Fees & payments", "icon": "wallet-cards", "resource": "fees"},
        {"slug": "finance", "label": "Finance", "icon": "landmark", "resource": "finance"},
    ],
    "operations": [
        {"slug": "library", "label": "Library", "icon": "library", "resource": "library"},
        {"slug": "communication", "label": "Communication", "icon": "messages-square", "resource": "communication"},
    ],
    "administration": [
        {"slug": "audit", "label": "Audit trail", "icon": "history", "resource": "audit"},
        {"slug": "settings", "label": "School settings", "icon": "settings-2", "resource": "settings"},
    ],
}

ROLE_RESOURCES = {
    "Admin": {"*"},
    "Head Teacher": {"*"},
    "Director of Studies": {
        "students", "staff", "admissions", "parents", "classes", "subjects", "results",
        "attendance", "timetable", "communication", "audit",
    },
    "Bursar": {"students", "fees", "finance", "communication", "audit"},
    "Class Teacher": {"students", "classes", "subjects", "results", "attendance", "timetable", "communication"},
    "Teacher": {"students", "classes", "subjects", "results", "attendance", "timetable", "communication"},
    "Admissions Officer": {"students", "admissions", "communication"},
    "Librarian": {"students", "library", "communication"},
    "Library Assistant": {"students", "library", "communication"},
    "Support Staff": {"communication"},
    "Parent": {"students", "results", "attendance", "fees", "communication"},
    "Staff": {"communication"},
}

GROUP_LABELS = {
    "overview": "Overview",
    "people": "People",
    "academics": "Academics",
    "finance": "Finance",
    "operations": "Operations",
    "administration": "Administration",
}


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
    groups = []
    for group_key, items in NAVIGATION.items():
        visible = []
        for item in items:
            resource = item["resource"]
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
    qs = Result.objects.select_related(
        "student", "assessment__assessment_type", "assessment__subject", "assessment__academic_class__Class",
        "batch",
    ).order_by("-id")
    role = canonical_role_label(_active_role(request))
    if role == "Parent":
        allowed_ids = _parent_accesses(request.user).filter(can_view_academics=True).values_list("student_id", flat=True)
        qs = qs.filter(student_id__in=allowed_ids)
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
    rows = [
        {
            "id": row.id,
            "student": row.student.student_name,
            "class": _str(row.academic_class.Class),
            "term": _str(row.academic_class.term),
            "bill_date": _date(row.bill_date),
            "due_date": _date(row.due_date),
            "billed": _money(row.total_amount),
            "paid": _money(row.amount_paid),
            "balance": _money(row.balance),
            "status": row.status,
        }
        for row in qs[:2000]
    ]
    return {
        "title": "Fees & payments",
        "description": "Student bills, receipts, credits and outstanding balances from the live fee ledger.",
        "columns": [["student", "Student"], ["class", "Class"], ["term", "Term"], ["billed", "Billed"], ["paid", "Paid"], ["balance", "Balance"], ["due_date", "Due date"], ["status", "Status"]],
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
    announcements = Announcement.objects.filter(is_active=True).order_by("-starts_at")
    events = Event.objects.filter(is_active=True).order_by("-start_datetime")
    if role == "Parent":
        announcements = announcements.filter(audience__in=["all", "parents"])
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
    "finance": _resource_finance,
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
        attendance = AttendanceSession.objects.filter(records__student_id__in=_parent_student_ids(request.user)).distinct().count()
        return [
            {"label": "Children", "value": student_qs.count(), "hint": "Linked to this account", "tone": "green"},
            {"label": "Outstanding fees", "value": _money(balance), "hint": "Across linked children", "tone": "gold", "currency": True},
            {"label": "Attendance sessions", "value": attendance, "hint": "Recorded sessions", "tone": "blue"},
            {"label": "Unread notices", "value": ParentNotification.objects.filter(user=request.user, read_at__isnull=True).count(), "hint": "Parent notifications", "tone": "violet"},
        ]

    if role == "Bursar":
        bills = StudentBill.objects.prefetch_related("items", "payments", "applied_credits")
        outstanding = sum((bill.balance for bill in bills), Decimal("0"))
        month_start = timezone.localdate().replace(day=1)
        payments = Payment.objects.filter(payment_date__gte=month_start).aggregate(total=Sum("amount"))["total"] or 0
        return [
            {"label": "Outstanding fees", "value": _money(outstanding), "hint": "Current ledger balance", "tone": "gold", "currency": True},
            {"label": "Payments this month", "value": _money(payments), "hint": f"Since {month_start:%d %b}", "tone": "green", "currency": True},
            {"label": "Student bills", "value": bills.count(), "hint": "Bills in the ledger", "tone": "blue"},
            {"label": "Pending expenditure", "value": Expenditure.objects.filter(payment_status__iexact="Pending").count(), "hint": "Awaiting settlement", "tone": "violet"},
        ]

    if role in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        allocations = ClassSubjectAllocation.objects.filter(subject_teacher=staff, is_active=True) if staff else ClassSubjectAllocation.objects.none()
        pending = ResultBatch.objects.filter(assessment__subject_id__in=allocations.values_list("subject_id", flat=True), status__in=["DRAFT", "PENDING"]).distinct().count()
        today_sessions = AttendanceSession.objects.filter(teacher=staff, date=timezone.localdate()).count() if staff else 0
        return [
            {"label": "My students", "value": student_qs.count(), "hint": "Across assigned classes", "tone": "green"},
            {"label": "Subject allocations", "value": allocations.count(), "hint": "Active teaching allocations", "tone": "blue"},
            {"label": "Results in progress", "value": pending, "hint": "Draft or pending verification", "tone": "gold"},
            {"label": "Today’s attendance", "value": today_sessions, "hint": "Sessions assigned today", "tone": "violet"},
        ]

    if role in {"Librarian", "Library Assistant"}:
        return [
            {"label": "Book titles", "value": LibraryBook.objects.count(), "hint": "Catalogue titles", "tone": "green"},
            {"label": "Available copies", "value": LibraryCopy.objects.filter(status="available").count(), "hint": "Ready to issue", "tone": "blue"},
            {"label": "Active loans", "value": LibraryLoan.objects.filter(returned_at__isnull=True).count(), "hint": "Currently borrowed", "tone": "gold"},
            {"label": "Outstanding fines", "value": LibraryFine.objects.filter(status="outstanding").count(), "hint": "Needs follow-up", "tone": "violet"},
        ]

    if role == "Admissions Officer":
        return [
            {"label": "Applications", "value": AdmissionApplication.objects.count(), "hint": "All applications", "tone": "green"},
            {"label": "Pending review", "value": AdmissionApplication.objects.exclude(status__in=["enrolled", "rejected"]).count(), "hint": "Still in workflow", "tone": "gold"},
            {"label": "Enrolled", "value": AdmissionApplication.objects.filter(enrolled_student__isnull=False).count(), "hint": "Converted to students", "tone": "blue"},
            {"label": "Active students", "value": Student.objects.filter(is_active=True).count(), "hint": "Current student register", "tone": "violet"},
        ]

    # Admin / Head Teacher / DOS / fallback staff summary.
    return [
        {"label": "Active students", "value": Student.objects.filter(is_active=True).count(), "hint": "Current student register", "tone": "green"},
        {"label": "Active staff", "value": Staff.objects.filter(staff_status="Active").count(), "hint": "Staff currently active", "tone": "blue"},
        {"label": "Pending admissions", "value": AdmissionApplication.objects.exclude(status__in=["enrolled", "rejected"]).count(), "hint": "Needs attention", "tone": "gold"},
        {"label": "Results awaiting verification", "value": ResultBatch.objects.filter(status="PENDING").count(), "hint": "Submitted batches", "tone": "violet"},
    ]


def _attention_items(request) -> list[dict[str, Any]]:
    role = canonical_role_label(_active_role(request))
    items = []
    if role in {"Admin", "Head Teacher", "Director of Studies"}:
        pending = ResultBatch.objects.filter(status="PENDING").count()
        if pending:
            items.append({"title": f"{pending} result batch{'es' if pending != 1 else ''} awaiting verification", "resource": "results", "severity": "warning"})
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
    notices = []
    for row in ResultVerificationNotification.objects.filter(recipient=request.user).order_by("-created_at")[:8]:
        notices.append({
            "id": f"verification-{row.id}", "title": row.title, "message": row.message,
            "created_at": _date(row.created_at), "read": row.read, "kind": "results",
        })
    for row in ParentNotification.objects.filter(user=request.user).order_by("-created_at")[:8]:
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
        return Response({
            **context,
            "role": canonical_role_label(_active_role(request)),
            "stats": _dashboard_stats(request),
            "attention": _attention_items(request),
            "notifications": _notifications(request),
        })


class WorkspaceResourceAPIView(WorkspaceBaseAPIView):
    def get(self, request, resource: str):
        builder = RESOURCE_BUILDERS.get(resource)
        if not builder:
            return Response({"detail": "Unknown workspace resource."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access(request, resource):
            return Response(
                {"code": "resource_forbidden", "detail": "Your current role does not have access to this workspace module."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from .workspace_forms import resource_action_policy

        payload = builder(request)
        rows = _search(payload.pop("rows"), request.query_params.get("q", ""))
        page = _paginate(request, rows)
        return Response({
            "resource": resource,
            **payload,
            "columns": [{"key": key, "label": label} for key, label in payload["columns"]],
            "actions": resource_action_policy(request, resource),
            **page,
        })


class WorkspaceResourceFormAPIView(WorkspaceBaseAPIView):
    def _check(self, request, resource: str, action: str):
        from .workspace_forms import RESOURCE_FORMS, resource_action_policy

        if resource not in RESOURCE_FORMS:
            return Response({"detail": "This module does not use the standard workspace form yet."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access(request, resource):
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
