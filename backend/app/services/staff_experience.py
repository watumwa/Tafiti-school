"""Shared staff capabilities and navigation for the authenticated application shell.

The active role intentionally drives the visible experience.  Backend views must
still enforce their own authorization; this module is presentation and workflow
policy, not a replacement for decorators.
"""
from __future__ import annotations

from django.conf import settings
from django.urls import NoReverseMatch, reverse


def normalize_role(value: str) -> str:
    return "-".join(str(value or "").strip().lower().replace("_", " ").split())


def active_role_for_request(request) -> str:
    if getattr(getattr(request, "user", None), "is_superuser", False):
        return "Admin"
    session_role = (request.session.get("active_role_name") or "").strip()
    if session_role:
        return session_role
    try:
        return request.user.staff_account.role.name
    except (AttributeError, TypeError):
        return "Support Staff"


def capabilities_for_request(request) -> dict[str, bool]:
    role = normalize_role(active_role_for_request(request))
    is_admin = role in {"admin", "super-admin"}
    is_head = role in {"head-teacher", "head-master", "headteacher", "headmaster", "principal"}
    is_dos = role in {"director-of-studies", "dos"}
    is_teacher = role in {"teacher", "subject-teacher"}
    is_class_teacher = role == "class-teacher"
    is_finance = role in {"bursar", "finance", "finance-manager", "cashier"}
    is_library = role in {"librarian", "library-assistant"}
    is_admissions = role == "admissions-officer"

    return {
        "is_admin": is_admin,
        "view_dashboard": is_admin or is_head or is_dos,
        "manage_settings": is_admin,
        "manage_users": is_admin,
        "manage_hr": is_admin,
        "view_students": is_admin or is_head or is_dos or is_teacher or is_class_teacher or is_finance or is_library,
        "manage_students": is_admin,
        "view_student_documents": is_admin or is_head or is_dos or is_class_teacher,
        "manage_student_documents": is_admin,
        "view_academics": is_admin or is_head or is_dos or is_teacher or is_class_teacher,
        "manage_academics": is_admin or is_dos,
        "view_attendance": is_admin or is_head or is_dos or is_teacher or is_class_teacher,
        "manage_attendance": is_admin or is_dos or is_class_teacher,
        "view_finance": is_admin or is_finance,
        "manage_finance": is_admin or is_finance,
        "view_library": bool(getattr(settings, "LIBRARY_ENABLED", False)) and (is_admin or is_head or is_library),
        "manage_library": bool(getattr(settings, "LIBRARY_ENABLED", False)) and (is_admin or is_library),
        "view_admissions": bool(getattr(settings, "ADMISSIONS_ENABLED", False)) and (is_admin or is_admissions),
        "manage_admissions": bool(getattr(settings, "ADMISSIONS_ENABLED", False)) and (is_admin or is_admissions),
        "view_communications": is_admin or is_head or is_dos or is_teacher or is_class_teacher,
        "manage_timetable": is_admin or is_dos,
        "view_pattern_library": is_admin,
    }


def _url(name: str, query: str = "") -> str:
    try:
        url = reverse(name)
    except NoReverseMatch:
        return "#"
    return f"{url}?{query}" if query else url


def _item(label: str, name: str, icon: str = "ph-circle", *, query: str = "", matches=(), children=None):
    return {
        "label": label,
        "url": _url(name, query) if name else "#!",
        "icon": icon,
        "matches": tuple(matches) or ((name,) if name else ()),
        "children": children or [],
    }


def _section(label: str, *items):
    return {"label": label, "items": [item for item in items if item]}


def navigation_for_request(request, capabilities=None):
    capabilities = capabilities or capabilities_for_request(request)
    role = normalize_role(active_role_for_request(request))
    current = getattr(getattr(request, "resolver_match", None), "url_name", "") or ""
    sections = []

    def mark(items):
        for item in items:
            mark(item["children"])
            item["active"] = current in item["matches"] or any(child["active"] for child in item["children"])
        return items

    if capabilities["is_admin"]:
        administration_items = [
            _item("Students", "student_page", "ph-student"),
            _item("Staff", "staff_page", "ph-identification-card"),
            _item("School setup", "settings_page", "ph-gear"),
            _item("Users", "user_list", "ph-users-three"),
        ]
        if getattr(settings, "PARENT_PORTAL_ENABLED", False):
            administration_items.append(_item("Parent accounts", "parent_access_management", "ph-users-four"))
        administration_items.append(_item("UI patterns", "ui_patterns", "ph-palette"))
        sections.extend([
            _section("Control tower",
                _item("Dashboard", "index_page", "ph-house-line"),
                _item("Analytics", "", "ph-chart-pie-slice", children=[
                    _item("Overview", "dashboard_overview"),
                    _item("Finance", "dashboard_finance"),
                    _item("Academics", "dashboard_academics"),
                    _item("Attendance", "dashboard_attendance"),
                    _item("Reports", "dashboard_reports"),
                ]),
            ),
            _section("Administration", *administration_items),
            _section("Academics",
                _item("Academic setup", "academic_class_page", "ph-books", children=[
                    _item("Classes", "class_page"), _item("Streams", "stream_page"),
                    _item("Subjects", "subjects_page"), _item("Subject allocation", "subject_allocation_page"),
                    _item("Academic classes", "academic_class_page"),
                ]),
                _item("Attendance", "attendance_dashboard", "ph-calendar-check", children=[
                    _item("Take attendance", "take_attendance"),
                    _item("Student report", "student_attendance_report"),
                    _item("Analysis", "attendance_analysis"),
                ]),
                _item("Results", "school_results_dashboard", "ph-graduation-cap", children=[
                    _item("Overview", "school_results_dashboard"), _item("Enter results", "add_results_page"),
                    _item("Bulk result import", "bulk_result_entry"), _item("Reports", "class_stream_filter"),
                    _item("Assessment setup", "assessment_create"), _item("Assessment types", "assesment_type_page"),
                    _item("Grading system", "add_grading_system_page"),
                ]),
                _item("Timetable", "timetable_center", "ph-calendar-blank", children=[
                    _item("Timetable builder", "timetable_center"), _item("Exam timetable", "exam_timetable"),
                ]),
            ),
        ])

    if capabilities["view_finance"]:
        finance_management = [
            _item("Finance dashboard", "financial_dashboard"),
            _item("Expenditure", "expenditure_page"),
            _item("Financial summary", "financial_summary_report"),
            _item("Income statement", "income_statement"),
        ]
        if capabilities["is_admin"]:
            finance_management.extend([
                _item("Income sources", "income_source_page"), _item("Expenses", "expense_page"),
                _item("Budget", "budget_page"), _item("Vendors", "vendor_page"),
                _item("Bank reconciliation", "bank_reconciliation"), _item("Approvals", "approval_workflow"),
                _item("Cash flow", "cash_flow"), _item("Vendor payments", "vendor_report"),
            ])
        sections.append(_section("Finance",
            _item("Quick payment", "quick_payment", "ph-lightning"),
            _item("Fees management", "student_bill_page", "ph-receipt", children=[
                _item("Student bills", "student_bill_page"), _item("Class bills", "class_bill_list"),
                _item("Bulk create bills", "bulk_create_class_bills"), _item("Fees status", "fees_status"),
                _item("Carry forward", "carry_forward_balances"), _item("Payment ledger", "payment_ledger"),
            ]),
            _item("Finance management", "financial_dashboard", "ph-chart-line-up", children=finance_management),
        ))

    if capabilities["view_library"]:
        sections.append(_section("Library",
            _item("Dashboard", "library_dashboard", "ph-chart-pie-slice"),
            _item("Books", "library_catalogue", "ph-books"),
            _item("Members", "library_members", "ph-users"),
            _item("Circulation", "library_loans", "ph-arrows-left-right"),
            _item("Issue book", "library_issue", "ph-arrow-square-out"),
            _item("Return book", "library_return_station", "ph-arrow-u-down-left"),
            _item("Overdue", "library_loans", "ph-clock", query="status=overdue"),
            _item("Fines", "library_fines", "ph-receipt"),
        ))

    if capabilities["view_admissions"]:
        sections.append(_section("Admissions",
            _item("Overview", "admission_dashboard", "ph-chart-pie-slice"),
            _item("Applications", "admission_list", "ph-files"),
            _item("New application", "admission_create", "ph-plus-circle"),
            _item("Waitlist", "admission_list", "ph-clock", query="status=waitlisted"),
        ))

    if not capabilities["is_admin"] and capabilities["view_academics"]:
        academic_items = []
        if capabilities["view_dashboard"]:
            academic_items.append(_item("Dashboard", "index_page", "ph-house-line"))
        academic_items.append(_item("Student directory", "student_page", "ph-student"))
        if capabilities["manage_attendance"]:
            academic_items.append(_item("Take attendance", "take_attendance", "ph-calendar-check"))
        if capabilities["view_attendance"]:
            academic_items.append(_item("Attendance report", "student_attendance_report", "ph-chart-bar"))
        if role not in {"head-teacher", "head-master", "headteacher", "headmaster", "principal"}:
            academic_items.extend([
                _item("Enter results", "add_results_page", "ph-pencil-simple"),
                _item("Academic reports", "class_stream_filter", "ph-file-text"),
            ])
        else:
            academic_items.extend([
                _item("Results overview", "school_results_dashboard", "ph-graduation-cap"),
                _item("Academic reports", "class_stream_filter", "ph-file-text"),
            ])
        if role in {"teacher", "subject-teacher"}:
            academic_items.append(_item("My timetable", "teacher_timetable", "ph-calendar-blank"))
        sections.append(_section("Teaching" if "teacher" in role else "School management", *academic_items))

    if capabilities["view_communications"]:
        sections.append(_section("Communication",
            _item("Announcements", "announcement_list", "ph-megaphone"),
            _item("Events", "event_list", "ph-calendar-dots"),
            _item("Messages", "message_inbox", "ph-chat-circle-text"),
        ))

    if not sections:
        sections.append(_section("Workspace", _item("Dashboard", "index_page", "ph-house-line")))

    for section in sections:
        mark(section["items"])
    return sections
