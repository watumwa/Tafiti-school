from __future__ import annotations

from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Q
from django.utils import timezone

from app.models import (
    AcademicClass,
    AdmissionApplication,
    AttendancePolicy,
    AttendanceRecord,
    AttendanceSession,
    AuditLog,
    ClassRegister,
    ClassSubjectAllocation,
    ParentAccess,
    Result,
    ResultBatch,
    Staff,
    StaffAccount,
    Student,
    StudentBill,
    Subject,
    Timetable,
    VerificationSample,
)
from app.models.attendance import AttendanceStatus

from .auth import canonical_role_label, resolve_active_role


CONTEXT_RESOURCES = {"students", "staff", "admissions", "classes", "subjects", "fees", "attendance"}


def _str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    return str(value)


def _date(value) -> str:
    if not value:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _money(value) -> str:
    try:
        return f"{Decimal(value or 0):,.0f}"
    except (InvalidOperation, TypeError, ValueError):
        return "0"


def _file_url(value) -> str:
    if not value:
        return ""
    try:
        return value.url
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


def _base_path(request) -> str:
    return resolve_active_role(request.user, _token_context(request)).dashboard_path


def _module_path(request, resource: str, *, query: dict | None = None) -> str:
    path = f"{_base_path(request)}/{resource}"
    return f"{path}?{urlencode(query)}" if query else path


def _entity_path(request, resource: str, pk: int, *, query: dict | None = None) -> str:
    path = f"{_module_path(request, resource)}/{pk}"
    return f"{path}?{urlencode(query)}" if query else path


def _tab(key, label, columns, rows, description, empty_title):
    return {
        "key": key,
        "label": label,
        "count": len(rows),
        "description": description,
        "columns": [{"key": item[0], "label": item[1]} for item in columns],
        "rows": rows,
        "empty_title": empty_title,
    }


def _detail_rows(items):
    return [{"field": label, "value": _str(value) or "—"} for label, value in items]


def _audit_rows(instance, limit=30):
    content_type = ContentType.objects.get_for_model(instance, for_concrete_model=False)
    return [
        {
            "when": _date(row.timestamp),
            "action": row.get_action_display(),
            "by": row.username or _str(row.user) or "System",
            "summary": row.object_repr or _str(instance),
        }
        for row in AuditLog.objects.filter(
            content_type=content_type,
            object_id=str(instance.pk),
        ).select_related("user").order_by("-timestamp")[:limit]
    ]


def can_view_student_finance(request, student) -> bool:
    role = canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)
    if request.user.is_superuser or role in {"Admin", "Head Teacher", "Bursar"}:
        return True
    if role == "Parent":
        return ParentAccess.objects.filter(
            user=request.user,
            student=student,
            is_active=True,
            is_verified=True,
            can_view_finance=True,
        ).exists()
    return False


def can_verify_results(request) -> bool:
    role = canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)
    return bool(request.user.is_superuser or role in {"Admin", "Head Teacher", "Director of Studies"})


def result_verification_queue(request):
    if not can_verify_results(request):
        raise PermissionError("Your current role cannot verify result batches.")

    status_filter = request.query_params.get("status", "PENDING").upper()
    if status_filter not in {"ALL", "PENDING", "FLAGGED", "VERIFIED", "DRAFT"}:
        status_filter = "PENDING"

    queryset = ResultBatch.objects.select_related(
        "assessment",
        "assessment__academic_class",
        "assessment__academic_class__Class",
        "assessment__academic_class__term",
        "assessment__subject",
        "assessment__assessment_type",
        "submitted_by",
    ).order_by("submitted_at", "id")
    if status_filter != "ALL":
        queryset = queryset.filter(status=status_filter)

    rows = []
    for batch in queryset[:2000]:
        samples = VerificationSample.objects.filter(result__batch=batch)
        reviewed = samples.exclude(checked_at__isnull=True).count()
        sample_count = samples.count()
        rows.append({
            "id": batch.id,
            "batch": f"Batch {batch.id}",
            "class": _str(batch.assessment.academic_class.Class),
            "subject": batch.assessment.subject.name,
            "assessment": batch.assessment.assessment_type.name,
            "submitted_by": _str(batch.submitted_by) or "—",
            "submitted": _date(batch.submitted_at) or "—",
            "progress": f"{reviewed}/{sample_count}",
            "status": batch.get_status_display(),
        })

    counts = {
        key: ResultBatch.objects.filter(status=key).count()
        for key in ("PENDING", "FLAGGED", "VERIFIED", "DRAFT")
    }
    return {
        "title": "Result verification queue",
        "description": "Review one submitted batch, make a decision, then continue directly to the next pending batch.",
        "columns": [
            ["batch", "Batch"], ["class", "Class"], ["subject", "Subject"],
            ["assessment", "Assessment"], ["submitted_by", "Submitted by"],
            ["submitted", "Submitted"], ["progress", "Samples reviewed"], ["status", "Status"],
        ],
        "rows": rows,
        "view": "verification",
        "filters": [
            {"value": "PENDING", "label": "Pending", "count": counts["PENDING"]},
            {"value": "FLAGGED", "label": "Corrections", "count": counts["FLAGGED"]},
            {"value": "VERIFIED", "label": "Verified", "count": counts["VERIFIED"]},
            {"value": "DRAFT", "label": "Drafts", "count": counts["DRAFT"]},
            {"value": "ALL", "label": "All", "count": sum(counts.values())},
        ],
        "active_filter": status_filter,
    }


def _student_workspace(request, pk: int):
    from .workspace import _scope_students
    from .workspace_forms import resource_action_policy

    student = _scope_students(
        request,
        Student.objects.select_related("current_class", "stream", "term", "academic_year"),
    ).get(pk=pk)
    register = ClassRegister.objects.filter(student=student).select_related(
        "academic_class_stream",
        "academic_class_stream__academic_class",
        "academic_class_stream__academic_class__Class",
        "academic_class_stream__stream",
    ).order_by("-academic_class_stream__academic_class__academic_year_id", "-id").first()
    academic_class = register.academic_class_stream.academic_class if register else AcademicClass.objects.filter(
        Class=student.current_class,
        academic_year=student.academic_year,
        term=student.term,
    ).first()

    can_view_finance = can_view_student_finance(request, student)

    results = list(student.results.select_related(
        "assessment__subject", "assessment__assessment_type", "assessment__academic_class__Class",
    ).order_by("-assessment__date", "assessment__subject__name")[:100])
    attendance = list(student.attendance_records.select_related(
        "session__subject", "session__class_stream",
    ).order_by("-session__date")[:100])
    bills = list(student.bills.select_related("academic_class__Class", "academic_class__term").prefetch_related(
        "items", "payments", "applied_credits",
    ).order_by("-bill_date")[:50]) if can_view_finance else []
    documents = list(student.documents.order_by("-uploaded_at")[:50])

    billed = sum((Decimal(bill.total_amount) for bill in bills), Decimal("0"))
    paid = sum((Decimal(bill.amount_paid) for bill in bills), Decimal("0"))
    outstanding = sum((Decimal(bill.balance) for bill in bills), Decimal("0"))
    marked_attendance = [row for row in attendance if row.status != "unmarked"]
    present = [row for row in marked_attendance if row.status in {"present", "late"}]
    attendance_rate = round((len(present) / len(marked_attendance)) * 100) if marked_attendance else 0
    average = student.results.aggregate(value=Avg("score"))["value"]

    class_href = _entity_path(request, "classes", academic_class.pk) if academic_class else ""
    tabs = [
        _tab("overview", "Overview", [("field", "Profile"), ("value", "Details")], _detail_rows([
            ("Student ID", student.display_student_id), ("Full name", student.student_name),
            ("Gender", student.get_gender_display()), ("Date of birth", _date(student.birthdate)),
            ("Nationality", student.nationality), ("Religion", student.religion),
            ("Address", student.address), ("Guardian", student.guardian),
            ("Relationship", student.relationship), ("Guardian contact", student.contact),
        ]), "Identity and guardian information held in the student master.", "No profile details are available."),
        _tab("academics", "Academics", [("field", "Academic context"), ("value", "Current placement")], _detail_rows([
            ("Academic year", student.academic_year), ("Term", student.term),
            ("Class", student.current_class), ("Stream", student.stream),
        ]), "Current placement and enrolment context.", "No academic placement is available."),
        _tab("results", "Results", [("date", "Date"), ("subject", "Subject"), ("assessment", "Assessment"), ("score", "Score"), ("grade", "Grade"), ("status", "Status")], [
            {"date": _date(row.assessment.date), "subject": row.assessment.subject.name, "assessment": row.assessment.assessment_type.name, "score": f"{_str(row.score)} / {row.assessment.out_of}", "grade": row.grade, "status": row.get_status_display()}
            for row in results
        ], "Verified and in-progress assessment results from Django's results engine.", "No results have been recorded for this student."),
        _tab("attendance", "Attendance", [("date", "Date"), ("subject", "Subject"), ("session", "Session"), ("status", "Status"), ("remarks", "Remarks")], [
            {"date": _date(row.session.date), "subject": row.session.subject.name, "session": _str(row.session.class_stream), "status": row.get_status_display(), "remarks": row.remarks or "—"}
            for row in attendance
        ], "Recent lesson attendance without leaving the student profile.", "No attendance has been recorded for this student."),
        _tab("fees", "Fees", [("bill", "Bill"), ("class", "Class"), ("term", "Term"), ("billed", "Billed (UGX)"), ("paid", "Paid (UGX)"), ("balance", "Balance (UGX)"), ("status", "Status")], [
            {"bill": f"Bill #{row.pk}", "class": _str(row.academic_class.Class), "term": _str(row.academic_class.term), "billed": _money(row.total_amount), "paid": _money(row.amount_paid), "balance": _money(row.balance), "status": row.status, "_links": {"bill": _entity_path(request, "fees", row.pk)}}
            for row in bills
        ], "Bills, payments and balances from the live student ledger.", "No fee records exist for this student."),
        _tab("documents", "Documents", [("type", "Document"), ("uploaded", "Uploaded"), ("file", "File")], [
            {"type": row.get_document_type_display(), "uploaded": _date(row.uploaded_at), "file": row.file.name.rsplit("/", 1)[-1] if row.file else "—"}
            for row in documents
        ], "Documents already attached to the student record.", "No documents have been uploaded."),
        _tab("history", "History", [("when", "When"), ("action", "Action"), ("by", "By"), ("summary", "Summary")], _audit_rows(student), "Auditable changes to this student record.", "No audit history was found."),
    ]

    actions = [
        {"label": "View results", "href": _entity_path(request, "students", student.pk, query={"tab": "results"}), "icon": "chart"},
        {"label": "Open fee account", "href": _entity_path(request, "students", student.pk, query={"tab": "fees"}), "icon": "wallet"},
        {"label": "Attendance", "href": _entity_path(request, "students", student.pk, query={"tab": "attendance"}), "icon": "attendance"},
        {"label": "Contact guardian", "href": _module_path(request, "communication", query={"recipient": student.guardian, "student": student.pk}), "icon": "message"},
    ]
    if resource_action_policy(request, "students")["edit"]:
        actions.insert(0, {"label": "Edit profile", "action": "edit", "icon": "edit", "primary": True})

    payload = {
        "resource": "students", "id": student.pk, "eyebrow": "Student workspace",
        "title": student.student_name, "subtitle": student.display_student_id,
        "photo": _file_url(student.photo), "status": "Active" if student.is_active else "Inactive",
        "metadata": [
            {"label": "Class", "value": _str(student.current_class), "href": class_href},
            {"label": "Stream", "value": _str(student.stream)},
            {"label": "Guardian", "value": student.guardian},
            {"label": "Contact", "value": student.contact},
        ],
        "metrics": [
            {"label": "Results", "value": len(results), "hint": f"Average {_str(round(average, 1))}%" if average is not None else "No average yet", "tone": "blue"},
            {"label": "Attendance", "value": f"{attendance_rate}%", "hint": f"{len(marked_attendance)} marked sessions", "tone": "green"},
            {"label": "Paid", "value": f"UGX {_money(paid)}", "hint": f"of UGX {_money(billed)} billed", "tone": "violet"},
            {"label": "Outstanding", "value": f"UGX {_money(outstanding)}", "hint": "Across current bills", "tone": "gold"},
        ],
        "tabs": tabs, "actions": actions,
    }
    if not can_view_finance:
        payload["tabs"] = [tab for tab in payload["tabs"] if tab.get("key") != "fees"]
        payload["actions"] = [action for action in payload["actions"] if action.get("label") != "Open fee account"]
        payload["metrics"] = [metric for metric in payload["metrics"] if metric.get("label") not in {"Paid", "Outstanding"}]
    return payload



def _staff_workspace(request, pk: int):
    from .workspace_forms import resource_action_policy

    staff = Staff.objects.prefetch_related("roles").get(pk=pk)
    allocations = list(ClassSubjectAllocation.objects.filter(subject_teacher=staff).select_related(
        "subject", "academic_class_stream", "academic_class_stream__academic_class__Class",
        "academic_class_stream__stream",
    ).order_by("subject__name")[:100])
    sessions = list(AttendanceSession.objects.filter(teacher=staff).select_related(
        "subject", "class_stream",
    ).order_by("-date")[:100])
    # StaffDocument exposes its reverse relation as ``documents``.  Using the
    # default Django accessor here caused every staff record workspace to fail
    # before it could render, including records with no documents.
    documents = list(staff.documents.order_by("-id")[:50])
    account = StaffAccount.objects.filter(staff=staff).select_related("user", "role").first()
    tabs = [
        _tab("overview", "Overview", [("field", "Profile"), ("value", "Details")], _detail_rows([
            ("Full name", staff), ("Gender", staff.get_gender_display()), ("Date of birth", _date(staff.birth_date)),
            ("Contact", staff.contacts), ("Email", staff.email), ("Address", staff.address),
        ]), "Staff identity and contact information.", "No profile details are available."),
        _tab("employment", "Employment", [("field", "Employment"), ("value", "Details")], _detail_rows([
            ("Department", staff.get_department_display()), ("Hire date", _date(staff.hire_date)),
            ("Qualification", staff.qualification), ("Roles", ", ".join(staff.roles.values_list("name", flat=True)) or "—"),
            ("Academic staff", "Yes" if staff.is_academic_staff else "No"),
            ("Administrator", "Yes" if staff.is_administrator_staff else "No"),
        ]), "Employment status and school responsibilities.", "No employment details are available."),
        _tab("teaching", "Teaching", [("class", "Class"), ("stream", "Stream"), ("subject", "Subject"), ("status", "Status")], [
            {"class": _str(row.academic_class_stream.academic_class.Class), "stream": _str(row.academic_class_stream.stream), "subject": row.subject.name, "status": "Active" if row.is_active else "Inactive", "_links": {"class": _entity_path(request, "classes", row.academic_class_stream.academic_class_id), "subject": _entity_path(request, "subjects", row.subject_id)}}
            for row in allocations
        ], "Classes and subjects assigned to this staff member.", "No teaching allocations have been assigned."),
        _tab("attendance", "Attendance", [("date", "Date"), ("class", "Class"), ("subject", "Subject"), ("status", "Status")], [
            {"date": _date(row.date), "class": _str(row.class_stream), "subject": row.subject.name, "status": "Locked" if row.is_locked else "Open"}
            for row in sessions
        ], "Recent attendance sessions taught by this staff member.", "No attendance sessions were found."),
        _tab("documents", "Documents", [("type", "Document"), ("file", "File")], [
            {"type": row.get_document_type_display(), "file": row.file.name.rsplit("/", 1)[-1] if row.file else "—"} for row in documents
        ], "Employment documents attached to this profile.", "No staff documents have been uploaded."),
        _tab("account", "Account & role", [("field", "Account"), ("value", "Details")], _detail_rows([
            ("Username", account.user.get_username() if account else "Not provisioned"),
            ("Account email", account.user.email if account else "—"),
            ("Primary role", account.role if account else "—"),
            ("Account active", "Yes" if account and account.user.is_active else "No"),
        ]), "Login identity and primary role.", "No account has been provisioned."),
        _tab("activity", "Activity", [("when", "When"), ("action", "Action"), ("by", "By"), ("summary", "Summary")], _audit_rows(staff), "Auditable changes to this staff record.", "No audit history was found."),
    ]
    actions = [
        {"label": "Teaching", "href": _entity_path(request, "staff", staff.pk, query={"tab": "teaching"}), "icon": "subject"},
        {"label": "Attendance", "href": _entity_path(request, "staff", staff.pk, query={"tab": "attendance"}), "icon": "attendance"},
        {"label": "Account & role", "href": _entity_path(request, "staff", staff.pk, query={"tab": "account"}), "icon": "user"},
    ]
    if resource_action_policy(request, "staff")["edit"]:
        actions.insert(0, {"label": "Edit staff", "action": "edit", "icon": "edit", "primary": True})
    return {
        "resource": "staff", "id": staff.pk, "eyebrow": "Staff workspace",
        "title": _str(staff), "subtitle": f"Staff #{staff.pk}", "photo": _file_url(staff.staff_photo),
        "status": staff.staff_status,
        "metadata": [
            {"label": "Department", "value": staff.get_department_display()},
            {"label": "Roles", "value": ", ".join(staff.roles.values_list("name", flat=True)) or "—"},
            {"label": "Email", "value": staff.email}, {"label": "Contact", "value": staff.contacts},
        ],
        "metrics": [
            {"label": "Teaching allocations", "value": len(allocations), "hint": "Active and historical", "tone": "blue"},
            {"label": "Attendance sessions", "value": len(sessions), "hint": "Most recent 100", "tone": "green"},
            {"label": "Documents", "value": len(documents), "hint": "Employment files", "tone": "violet"},
            {"label": "Account", "value": "Active" if account and account.user.is_active else "Not active", "hint": "School login", "tone": "gold"},
        ],
        "tabs": tabs, "actions": actions,
    }


def _admission_workspace(request, pk: int):
    from .workspace_forms import resource_action_policy

    application = AdmissionApplication.objects.select_related(
        "cycle", "cycle__academic_year", "applying_class", "preferred_stream", "enrolled_student", "created_by",
    ).prefetch_related("status_history__changed_by").get(pk=pk)
    history = list(application.status_history.all()[:100])
    tabs = [
        _tab("applicant", "Applicant", [("field", "Applicant"), ("value", "Details")], _detail_rows([
            ("Application number", application.application_number), ("Student name", application.student_name),
            ("Gender", application.get_gender_display()), ("Date of birth", _date(application.birthdate)),
            ("Nationality", application.nationality), ("Religion", application.religion), ("Address", application.address),
        ]), "Applicant identity and contact details.", "No applicant details are available."),
        _tab("guardian", "Guardian", [("field", "Guardian"), ("value", "Details")], _detail_rows([
            ("Guardian", application.guardian), ("Relationship", application.relationship), ("Contact", application.contact),
        ]), "Primary guardian details supplied with the application.", "No guardian details are available."),
        _tab("previous-school", "Previous school", [("field", "Education"), ("value", "Details")], _detail_rows([
            ("Previous school", application.previous_school or "Not supplied"),
        ]), "Previous school information supplied by the applicant.", "No previous school was supplied."),
        _tab("placement", "Placement", [("field", "Placement"), ("value", "Details")], _detail_rows([
            ("Admission cycle", application.cycle), ("Academic year", application.cycle.academic_year),
            ("Applying class", application.applying_class), ("Preferred stream", application.preferred_stream or "Not selected"),
            ("Status", application.get_status_display()), ("Source", application.get_source_display()),
        ]), "Placement choices and current workflow state.", "No placement information is available."),
        _tab("notes", "Notes", [("field", "Notes"), ("value", "Details")], _detail_rows([
            ("Internal notes", application.internal_notes or "—"), ("Decision notes", application.decision_notes or "—"),
        ]), "Internal review and decision notes.", "No notes have been added."),
        _tab("timeline", "Timeline", [("when", "When"), ("from", "From"), ("to", "To"), ("by", "Changed by"), ("notes", "Notes")], [
            {"when": _date(row.changed_at), "from": dict(AdmissionApplication.STATUS_CHOICES).get(row.from_status, row.from_status or "New"), "to": dict(AdmissionApplication.STATUS_CHOICES).get(row.to_status, row.to_status), "by": _str(row.changed_by) or "System", "notes": row.notes or "—"}
            for row in history
        ], "Every recorded application status transition.", "No status transitions have been recorded."),
    ]
    actions = []
    if application.enrolled_student_id:
        actions.append({"label": "Open student profile", "href": _entity_path(request, "students", application.enrolled_student_id), "icon": "student", "primary": True})
    if resource_action_policy(request, "admissions")["edit"]:
        actions.append({"label": "Review application", "action": "edit", "icon": "edit", "primary": not actions})
    actions.extend([
        {"label": "Placement", "href": _entity_path(request, "admissions", application.pk, query={"tab": "placement"}), "icon": "class"},
        {"label": "Timeline", "href": _entity_path(request, "admissions", application.pk, query={"tab": "timeline"}), "icon": "history"},
    ])
    return {
        "resource": "admissions", "id": application.pk, "eyebrow": "Admission workspace",
        "title": application.student_name, "subtitle": application.application_number,
        "photo": "", "status": application.get_status_display(),
        "metadata": [
            {"label": "Applying for", "value": _str(application.applying_class)},
            {"label": "Preferred stream", "value": _str(application.preferred_stream) or "—"},
            {"label": "Guardian", "value": application.guardian},
            {"label": "Updated", "value": _date(application.updated_at)},
        ],
        "metrics": [
            {"label": "Workflow", "value": application.get_status_display(), "hint": application.get_source_display(), "tone": "blue"},
            {"label": "Timeline events", "value": len(history), "hint": "Recorded transitions", "tone": "green"},
            {"label": "Consent", "value": "Captured" if application.privacy_consent_at else "Not captured", "hint": "Privacy consent", "tone": "violet"},
            {"label": "Student record", "value": "Created" if application.enrolled_student_id else "Not yet", "hint": "Enrollment outcome", "tone": "gold"},
        ],
        "tabs": tabs, "actions": actions,
    }


def _class_workspace(request, pk: int):
    from .workspace import _active_role, _staff_for_user

    role = canonical_role_label(_active_role(request))
    queryset = AcademicClass.objects.select_related("Class", "section", "academic_year", "term").prefetch_related(
        "class_streams__stream", "class_streams__class_teacher",
    )
    if role in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        queryset = queryset.filter(Q(class_streams__class_teacher=staff) | Q(class_streams__subjects__subject_teacher=staff)).distinct() if staff else queryset.none()
    academic_class = queryset.get(pk=pk)
    streams = list(academic_class.class_streams.select_related("stream", "class_teacher").all())
    registers = list(ClassRegister.objects.filter(academic_class_stream__academic_class=academic_class).select_related(
        "student", "academic_class_stream__stream",
    ).order_by("student__student_name")[:500])
    allocations = list(ClassSubjectAllocation.objects.filter(academic_class_stream__academic_class=academic_class).select_related(
        "subject", "subject_teacher", "academic_class_stream__stream",
    ).order_by("subject__name")[:300])
    sessions = list(AttendanceSession.objects.filter(class_stream__academic_class=academic_class).select_related(
        "class_stream__stream", "subject", "teacher",
    ).order_by("-date")[:100])
    batches = list(ResultBatch.objects.filter(assessment__academic_class=academic_class).select_related(
        "assessment__subject", "assessment__assessment_type", "submitted_by",
    ).order_by("-id")[:100])
    timetable = list(Timetable.objects.filter(class_stream__academic_class=academic_class).select_related(
        "class_stream__stream", "subject", "teacher", "time_slot", "classroom",
    ).order_by("weekday", "time_slot__start_time")[:200])
    teacher_ids = {row.class_teacher_id for row in streams} | {row.subject_teacher_id for row in allocations}
    teachers = Staff.objects.filter(pk__in=teacher_ids).order_by("first_name", "last_name")
    tabs = [
        _tab("overview", "Overview", [("field", "Class"), ("value", "Details")], _detail_rows([
            ("Class", academic_class.Class), ("Section", academic_class.section),
            ("Academic year", academic_class.academic_year), ("Term", academic_class.term),
            ("Configured class fee", f"UGX {_money(academic_class.fees_amount)}"),
        ]), "Academic class configuration for this term.", "No class details are available."),
        _tab("streams", "Streams & teachers", [("stream", "Stream"), ("teacher", "Class teacher"), ("students", "Students"), ("subjects", "Subjects")], [
            {
                "stream": _str(row.stream),
                "teacher": _str(row.class_teacher) or "Unassigned",
                "students": ClassRegister.objects.filter(academic_class_stream=row).count(),
                "subjects": row.subjects.filter(is_active=True).count(),
                "_links": {"teacher": _entity_path(request, "staff", row.class_teacher_id)} if row.class_teacher_id else {},
            }
            for row in streams
        ], "Each stream, its class teacher and register size.", "No streams are configured for this class."),
        _tab("students", "Students", [("student_id", "Student ID"), ("student", "Student"), ("stream", "Stream"), ("status", "Status")], [
            {"student_id": row.student.display_student_id, "student": row.student.student_name, "stream": _str(row.academic_class_stream.stream), "status": "Active" if row.student.is_active else "Inactive", "_links": {"student": _entity_path(request, "students", row.student_id)}}
            for row in registers
        ], "Every learner registered in this class and its streams.", "No students are registered in this class."),
        _tab("subjects", "Subjects", [("subject", "Subject"), ("stream", "Stream"), ("teacher", "Teacher"), ("status", "Status")], [
            {"subject": row.subject.name, "stream": _str(row.academic_class_stream.stream), "teacher": _str(row.subject_teacher), "status": "Active" if row.is_active else "Inactive", "_links": {"subject": _entity_path(request, "subjects", row.subject_id), "teacher": _entity_path(request, "staff", row.subject_teacher_id)}}
            for row in allocations
        ], "Subject allocation and teaching context in one place.", "No subjects are allocated to this class."),
        _tab("teachers", "Teachers", [("teacher", "Teacher"), ("department", "Department"), ("status", "Status")], [
            {"teacher": _str(row), "department": row.get_department_display(), "status": row.staff_status, "_links": {"teacher": _entity_path(request, "staff", row.pk)}} for row in teachers
        ], "Class and subject teachers connected to this class.", "No teachers are connected to this class."),
        _tab("attendance", "Attendance", [("date", "Date"), ("stream", "Stream"), ("subject", "Subject"), ("teacher", "Teacher"), ("status", "Status")], [
            {"date": _date(row.date), "stream": _str(row.class_stream.stream), "subject": row.subject.name, "teacher": _str(row.teacher), "status": "Locked" if row.is_locked else "Open"}
            for row in sessions
        ], "Recent attendance sessions for this class.", "No attendance sessions have been created."),
        _tab("results", "Results", [("batch", "Batch"), ("subject", "Subject"), ("assessment", "Assessment"), ("submitted", "Submitted"), ("status", "Status")], [
            {"batch": f"Batch {row.pk}", "subject": row.assessment.subject.name, "assessment": row.assessment.assessment_type.name, "submitted": _date(row.submitted_at) or "—", "status": row.get_status_display(), "_links": {"batch": _entity_path(request, "results", row.pk, query={"view": "verification"}) if can_verify_results(request) else _module_path(request, "results", query={"q": row.assessment.subject.name})}}
            for row in batches
        ], "Assessment batches and verification state for this class.", "No result batches exist for this class."),
        _tab("timetable", "Timetable", [("day", "Day"), ("time", "Time"), ("stream", "Stream"), ("subject", "Subject"), ("teacher", "Teacher"), ("room", "Room")], [
            {"day": row.get_weekday_display(), "time": _str(row.time_slot), "stream": _str(row.class_stream.stream), "subject": row.subject.name, "teacher": _str(row.teacher) or "—", "room": _str(row.classroom) or "—"}
            for row in timetable
        ], "The class timetable without leaving the class workspace.", "No timetable entries exist for this class."),
    ]
    return {
        "resource": "classes", "id": academic_class.pk, "eyebrow": "Class workspace",
        "title": _str(academic_class.Class), "subtitle": f"{academic_class.academic_year} · {academic_class.term}",
        "photo": "", "status": "Current" if getattr(academic_class.academic_year, "is_current", False) else "Academic class",
        "metadata": [
            {"label": "Section", "value": _str(academic_class.section)},
            {"label": "Streams", "value": ", ".join(_str(row.stream) for row in streams) or "—"},
            {"label": "Academic year", "value": _str(academic_class.academic_year)},
            {"label": "Term", "value": _str(academic_class.term)},
        ],
        "metrics": [
            {"label": "Students", "value": len(registers), "hint": "Across configured streams", "tone": "blue"},
            {"label": "Subjects", "value": len({row.subject_id for row in allocations}), "hint": "Allocated subjects", "tone": "green"},
            {"label": "Teachers", "value": teachers.count(), "hint": "Class and subject teachers", "tone": "violet"},
            {"label": "Pending results", "value": sum(1 for row in batches if row.status == "PENDING"), "hint": "Awaiting verification", "tone": "gold"},
        ],
        "tabs": tabs,
        "can_register": bool(request.user.is_superuser or role in {"Admin", "Head Teacher", "Director of Studies"}),
        "can_promote": bool(
            (request.user.is_superuser or role in {"Admin", "Director of Studies"})
            and academic_class.term.is_current
            and str(academic_class.term.term) == "3"
        ),
        "actions": [
            {"label": "Students", "href": _entity_path(request, "classes", academic_class.pk, query={"tab": "students"}), "icon": "student", "primary": True},
            {"label": "Subjects", "href": _module_path(request, "subjects", query={"class": academic_class.pk}), "icon": "book-open"},
            {"label": "Take attendance", "href": _module_path(request, "attendance", query={"class": academic_class.pk}), "icon": "attendance"},
            {"label": "Class results", "href": _entity_path(request, "classes", academic_class.pk, query={"tab": "results"}), "icon": "chart"},
            {"label": "Timetable", "href": _module_path(request, "timetable", query={"class": academic_class.pk}), "icon": "calendar-days"},
            {"label": "Send announcement", "href": _module_path(request, "communication", query={"class": academic_class.pk}), "icon": "message"},
        ],
    }


def _subject_workspace(request, pk: int):
    from .workspace import _active_role, _staff_for_user

    queryset = Subject.objects.select_related("section")
    if canonical_role_label(_active_role(request)) in {"Teacher", "Class Teacher"}:
        staff = _staff_for_user(request.user)
        queryset = queryset.filter(subjects__subject_teacher=staff, subjects__is_active=True).distinct() if staff else queryset.none()
    subject = queryset.get(pk=pk)
    allocations = list(ClassSubjectAllocation.objects.filter(subject=subject).select_related(
        "academic_class_stream", "academic_class_stream__academic_class__Class", "academic_class_stream__academic_class__academic_year",
        "academic_class_stream__stream", "subject_teacher",
    ).order_by("academic_class_stream__academic_class__Class__name")[:300])
    assessments = list(subject.assessments.select_related(
        "assessment_type", "academic_class__Class", "academic_class__term", "academic_class__academic_year",
    ).order_by("-date")[:100])
    results = Result.objects.filter(assessment__subject=subject)
    average = results.aggregate(value=Avg("score"))["value"]
    teachers = Staff.objects.filter(pk__in={row.subject_teacher_id for row in allocations}).order_by("first_name", "last_name")
    class_ids = {row.academic_class_stream.academic_class_id for row in allocations}
    tabs = [
        _tab("overview", "Overview", [("field", "Subject"), ("value", "Details")], _detail_rows([
            ("Code", subject.code), ("Name", subject.name), ("Section", subject.section),
            ("Type", subject.get_type_display()), ("Credit hours", subject.credit_hours),
            ("Description", subject.description or "—"),
        ]), "Core subject configuration.", "No subject details are available."),
        _tab("classes", "Classes", [("class", "Class"), ("stream", "Stream"), ("year", "Academic year"), ("teacher", "Teacher"), ("status", "Status")], [
            {"class": _str(row.academic_class_stream.academic_class.Class), "stream": _str(row.academic_class_stream.stream), "year": _str(row.academic_class_stream.academic_class.academic_year), "teacher": _str(row.subject_teacher), "status": "Active" if row.is_active else "Inactive", "_links": {"class": _entity_path(request, "classes", row.academic_class_stream.academic_class_id), "teacher": _entity_path(request, "staff", row.subject_teacher_id)}}
            for row in allocations
        ], "Every class and stream where this subject is allocated.", "This subject has not been allocated to a class."),
        _tab("teachers", "Teachers", [("teacher", "Teacher"), ("department", "Department"), ("status", "Status")], [
            {"teacher": _str(row), "department": row.get_department_display(), "status": row.staff_status, "_links": {"teacher": _entity_path(request, "staff", row.pk)}} for row in teachers
        ], "Teachers currently connected through subject allocation.", "No teachers are assigned to this subject."),
        _tab("assessments", "Assessments", [("date", "Date"), ("class", "Class"), ("assessment", "Assessment"), ("out_of", "Out of"), ("status", "Status")], [
            {"date": _date(row.date), "class": _str(row.academic_class.Class), "assessment": row.assessment_type.name, "out_of": row.out_of, "status": "Completed" if row.is_done else "In progress", "_links": {"class": _entity_path(request, "classes", row.academic_class_id)}}
            for row in assessments
        ], "Assessments configured for this subject.", "No assessments exist for this subject."),
        _tab("performance", "Performance", [("field", "Performance"), ("value", "Current measure")], _detail_rows([
            ("Recorded results", results.count()), ("Average raw score", round(average, 1) if average is not None else "No results"),
            ("Verified results", results.filter(status="VERIFIED").count()), ("Classes allocated", len(class_ids)),
        ]), "A concise view of existing result coverage.", "No performance data is available."),
    ]
    return {
        "resource": "subjects", "id": subject.pk, "eyebrow": "Subject workspace",
        "title": subject.name, "subtitle": subject.code, "photo": "", "status": subject.get_type_display(),
        "metadata": [
            {"label": "Section", "value": _str(subject.section)}, {"label": "Type", "value": subject.get_type_display()},
            {"label": "Credit hours", "value": _str(subject.credit_hours)}, {"label": "Teachers", "value": _str(teachers.count())},
        ],
        "metrics": [
            {"label": "Classes", "value": len(class_ids), "hint": "With active or historic allocations", "tone": "blue"},
            {"label": "Teachers", "value": teachers.count(), "hint": "Allocated teachers", "tone": "green"},
            {"label": "Assessments", "value": len(assessments), "hint": "Most recent 100", "tone": "violet"},
            {"label": "Average score", "value": f"{round(average, 1)}%" if average is not None else "—", "hint": "Across recorded results", "tone": "gold"},
        ],
        "tabs": tabs,
        "actions": [
            {"label": "Assessments", "href": _entity_path(request, "subjects", subject.pk, query={"tab": "assessments"}), "icon": "chart", "primary": True},
            {"label": "View results", "href": _module_path(request, "results", query={"subject": subject.pk, "q": subject.name}), "icon": "result"},
            {"label": "Classes", "href": _entity_path(request, "subjects", subject.pk, query={"tab": "classes"}), "icon": "class"},
        ],
    }


def _fee_workspace(request, pk: int):
    from .workspace import _is_parent_context, _parent_accesses

    queryset = StudentBill.objects.select_related(
        "student", "student__current_class", "student__stream", "academic_class__Class", "academic_class__term",
    ).prefetch_related("items", "payments", "applied_credits", "student__credits")
    if _is_parent_context(request):
        student_ids = _parent_accesses(request.user).filter(can_view_finance=True).values_list("student_id", flat=True)
        queryset = queryset.filter(student_id__in=student_ids)
    anchor = queryset.get(pk=pk)
    student = anchor.student
    bills = list(queryset.filter(student=student).order_by("-bill_date"))
    payments = [payment for bill in bills for payment in bill.payments.all()]
    credits = list(student.credits.select_related("original_bill", "applied_to_bill").order_by("-created_date")[:100])
    billed = sum((Decimal(row.total_amount) for row in bills), Decimal("0"))
    paid = sum((Decimal(row.amount_paid) for row in bills), Decimal("0"))
    balance = sum((Decimal(row.balance) for row in bills), Decimal("0"))
    available_credit = sum((Decimal(row.amount) for row in credits if not row.is_applied and row.amount > 0), Decimal("0"))
    tabs = [
        _tab("statement", "Statement", [("date", "Date"), ("reference", "Reference"), ("description", "Description"), ("debit", "Debit (UGX)"), ("credit", "Credit (UGX)"), ("status", "Status")], sorted([
            {"date": _date(row.bill_date), "reference": f"Bill #{row.pk}", "description": f"{row.academic_class.Class} · {row.academic_class.term}", "debit": _money(row.total_amount), "credit": "—", "status": row.status}
            for row in bills
        ] + [
            {"date": _date(row.payment_date), "reference": row.reference_no, "description": f"Payment · {row.payment_method}", "debit": "—", "credit": _money(row.amount), "status": "Recorded"}
            for row in payments
        ], key=lambda item: item["date"], reverse=True), "A single chronological view of bills and payments.", "No statement entries exist for this student."),
        _tab("bills", "Bills", [("bill", "Bill"), ("class", "Class"), ("term", "Term"), ("billed", "Billed (UGX)"), ("paid", "Paid (UGX)"), ("balance", "Balance (UGX)"), ("due", "Due date"), ("status", "Status")], [
            {"bill": f"Bill #{row.pk}", "class": _str(row.academic_class.Class), "term": _str(row.academic_class.term), "billed": _money(row.total_amount), "paid": _money(row.amount_paid), "balance": _money(row.balance), "due": _date(row.due_date) or "—", "status": row.status}
            for row in bills
        ], "All bills for this student account.", "No bills exist for this student."),
        _tab("payments", "Payments", [("date", "Date"), ("receipt", "Receipt / reference"), ("method", "Method"), ("category", "Category"), ("amount", "Amount (UGX)"), ("recorded_by", "Recorded by")], [
            {"date": _date(row.payment_date), "receipt": row.reference_no, "method": row.payment_method, "category": row.fee_category or "—", "amount": _money(row.amount), "recorded_by": row.recorded_by}
            for row in sorted(payments, key=lambda item: item.payment_date, reverse=True)
        ], "Payments stay connected to the student account that received them.", "No payments have been recorded for this student."),
        _tab("credits", "Credits", [("date", "Date"), ("description", "Description"), ("amount", "Amount (UGX)"), ("status", "Status")], [
            {"date": _date(row.created_date), "description": row.description, "amount": _money(row.amount), "status": "Applied" if row.is_applied else "Available"} for row in credits
        ], "Available and applied student credits.", "No credits exist for this student."),
    ]
    return {
        "resource": "fees", "id": anchor.pk, "eyebrow": "Student fee account",
        "title": student.student_name, "subtitle": student.display_student_id,
        "photo": _file_url(student.photo), "status": "Outstanding" if balance > 0 else "Settled",
        "metadata": [
            {"label": "Class", "value": _str(student.current_class)}, {"label": "Stream", "value": _str(student.stream)},
            {"label": "Bills", "value": _str(len(bills))}, {"label": "Latest bill", "value": f"#{anchor.pk}"},
        ],
        "metrics": [
            {"label": "Total billed", "value": f"UGX {_money(billed)}", "hint": "Across all bills", "tone": "blue"},
            {"label": "Paid", "value": f"UGX {_money(paid)}", "hint": f"{len(payments)} payment records", "tone": "green"},
            {"label": "Available credit", "value": f"UGX {_money(available_credit)}", "hint": "Not yet applied", "tone": "violet"},
            {"label": "Outstanding", "value": f"UGX {_money(balance)}", "hint": "Current account balance", "tone": "gold"},
        ],
        "tabs": tabs,
        "actions": [
            {"label": "View payments", "href": _entity_path(request, "fees", anchor.pk, query={"tab": "payments"}), "icon": "wallet", "primary": True},
            {"label": "Open student profile", "href": _entity_path(request, "students", student.pk, query={"tab": "fees"}), "icon": "student"},
            {"label": "Statement", "href": _entity_path(request, "fees", anchor.pk, query={"tab": "statement"}), "icon": "report"},
            {"label": "Contact guardian", "href": _module_path(request, "communication", query={"recipient": student.guardian, "student": student.pk}), "icon": "message"},
        ],
    }


def _result_verification_workspace(request, pk: int):
    if not can_verify_results(request):
        raise PermissionError("Your current role cannot verify result batches.")
    batch = ResultBatch.objects.select_related(
        "assessment", "assessment__academic_class", "assessment__academic_class__Class",
        "assessment__academic_class__term", "assessment__academic_class__academic_year",
        "assessment__subject", "assessment__assessment_type", "submitted_by", "verified_by",
    ).get(pk=pk)
    samples = list(VerificationSample.objects.filter(result__batch=batch).select_related(
        "result", "result__student", "checked_by",
    ).order_by("result__student__student_name"))
    reviewed = sum(1 for row in samples if row.checked_at)
    matched = sum(1 for row in samples if row.matched is True)
    mismatched = sum(1 for row in samples if row.matched is False)
    next_batch = ResultBatch.objects.filter(status="PENDING").exclude(pk=batch.pk).order_by("submitted_at", "id").first()
    can_finalize = batch.status == "PENDING" and batch.submitted_by_id != request.user.id
    sample_rows = [
        {"student_id": row.result.student.display_student_id, "student": row.result.student.student_name, "verifier_mark": _str(row.dos_mark) or "Not entered", "reviewed_by": _str(row.checked_by) or "—", "status": "Matched" if row.matched is True else ("Mismatch" if row.matched is False else "Pending"), "_links": {"student": _entity_path(request, "students", row.result.student_id)}}
        for row in samples
    ]
    return {
        "resource": "results", "id": batch.pk, "eyebrow": "Result verification",
        "title": f"{batch.assessment.subject.name} · {batch.assessment.assessment_type.name}",
        "subtitle": f"{batch.assessment.academic_class.Class} · {batch.assessment.academic_class.term}",
        "photo": "", "status": batch.get_status_display(),
        "metadata": [
            {"label": "Academic year", "value": _str(batch.assessment.academic_class.academic_year)},
            {"label": "Submitted by", "value": _str(batch.submitted_by) or "—"},
            {"label": "Submitted", "value": _date(batch.submitted_at) or "—"},
            {"label": "Out of", "value": _str(batch.assessment.out_of)},
        ],
        "metrics": [
            {"label": "Scripts", "value": batch.results.count(), "hint": "In this submitted batch", "tone": "blue"},
            {"label": "Samples", "value": len(samples), "hint": "Selected by Django", "tone": "green"},
            {"label": "Reviewed", "value": f"{reviewed}/{len(samples)}", "hint": "Verifier marks entered", "tone": "violet"},
            {"label": "Differences", "value": mismatched, "hint": "Require correction if non-zero", "tone": "gold"},
        ],
        "tabs": [
            _tab("samples", "Verification samples", [("student_id", "Student ID"), ("student", "Student"), ("verifier_mark", "Verifier mark"), ("reviewed_by", "Reviewed by"), ("status", "Comparison")], sample_rows, "Teacher marks stay hidden until independent re-entry is complete.", "No verification samples were selected for this batch."),
            _tab("summary", "Decision summary", [("field", "Verification"), ("value", "Current state")], _detail_rows([
                ("Batch status", batch.get_status_display()), ("Samples selected", len(samples)),
                ("Reviewed", reviewed), ("Matches", matched), ("Differences", mismatched),
                ("Verified by", batch.verified_by or "—"), ("Verified at", _date(batch.verified_at) or "—"),
                ("Correction reason", batch.rejection_reason or "—"),
            ]), "The current verification decision and audit context.", "No verification summary is available."),
        ],
        "actions": [
            {"label": "Back to pending queue", "href": _module_path(request, "results", query={"view": "verification", "status": "PENDING"}), "icon": "queue", "primary": not can_finalize},
            *([{"label": "Next pending batch", "href": _entity_path(request, "results", next_batch.pk, query={"view": "verification"}), "icon": "next"}] if next_batch else []),
        ],
        "workflow": {
            "kind": "result_verification",
            "can_finalize": can_finalize,
            "blocked_reason": (
                "You cannot verify a batch you submitted. Ask another authorised verifier to complete it."
                if batch.status == "PENDING" and batch.submitted_by_id == request.user.id
                else ("This batch is no longer pending verification." if batch.status != "PENDING" else "")
            ),
            "out_of": batch.assessment.out_of,
            "samples": [
                {"sample_id": row.pk, "student": row.result.student.student_name, "student_id": row.result.student.display_student_id, "value": _str(row.dos_mark), "checked": bool(row.checked_at)}
                for row in samples
            ],
            "next_href": _entity_path(request, "results", next_batch.pk, query={"view": "verification"}) if next_batch else "",
        },
    }


def build_entity_workspace(request, resource: str, pk: int):
    if resource == "results" and request.query_params.get("view") == "verification":
        return _result_verification_workspace(request, pk)
    builders = {
        "students": _student_workspace,
        "staff": _staff_workspace,
        "admissions": _admission_workspace,
        "classes": _class_workspace,
        "subjects": _subject_workspace,
        "fees": _fee_workspace,
        "attendance": _attendance_workspace,
    }
    builder = builders.get(resource)
    if not builder:
        raise KeyError(resource)
    return builder(request, pk)


def _attendance_workspace(request, pk: int):
    from .workspace import _parent_accesses, _staff_for_user

    session = AttendanceSession.objects.select_related(
        "class_stream__academic_class__Class",
        "class_stream__stream",
        "subject",
        "teacher",
        "academic_year",
        "term",
        "time_slot",
    ).get(pk=pk)
    role = canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)
    is_admin = bool(request.user.is_superuser or role == "Admin")
    is_manager = role in {"Admin", "Head Teacher", "Director of Studies"}
    staff = _staff_for_user(request.user)
    is_assigned_teacher = role in {"Teacher", "Class Teacher"} and staff and session.teacher_id == staff.pk

    parent_student_ids = None
    if role == "Parent":
        access = _parent_accesses(request.user).filter(can_view_attendance=True)
        if not session.records.filter(student_id__in=access.values_list("student_id", flat=True)).exists():
            raise PermissionError("This attendance session is not available to this parent account.")
        parent_student_ids = access.values_list("student_id", flat=True)
    elif role in {"Teacher", "Class Teacher"} and not is_assigned_teacher:
        raise PermissionError("You can only open attendance sessions assigned to you.")

    registered_student_ids = ClassRegister.objects.filter(
        academic_class_stream=session.class_stream,
    ).values_list("student_id", flat=True)
    registered_students = Student.objects.filter(
        pk__in=registered_student_ids,
    ).order_by("student_name")
    if parent_student_ids is not None:
        registered_students = registered_students.filter(pk__in=parent_student_ids)
    records_by_student = {
        row.student_id: row
        for row in AttendanceRecord.objects.filter(
            session=session,
            student__in=registered_students,
        ).select_related("student", "captured_by")
    }
    students = [
        {
            "student_id": student.pk,
            "student_name": student.student_name,
            "display_id": student.display_student_id,
            "status": records_by_student[student.pk].status if student.pk in records_by_student else AttendanceStatus.UNMARKED,
            "remarks": records_by_student[student.pk].remarks if student.pk in records_by_student else "",
        }
        for student in registered_students
    ]
    counts = {value: 0 for value, _ in AttendanceStatus.choices}
    for student in students:
        counts[student["status"]] += 1

    policy = AttendancePolicy.objects.first()
    can_edit = bool(
        role != "Parent"
        and (is_manager or is_assigned_teacher)
        and (
            not session.is_locked
            or bool(is_assigned_teacher and policy and policy.allow_teacher_edit_locked_sessions)
        )
    )
    can_unlock = bool(is_admin and session.is_locked)
    status_label = "Locked" if session.is_locked else "Open"
    class_stream = session.class_stream
    return {
        "resource": "attendance",
        "id": session.pk,
        "eyebrow": "Attendance session",
        "title": f"{class_stream.academic_class.Class} · {class_stream.stream}",
        "subtitle": f"{session.subject.name} · {session.date:%d %b %Y}",
        "photo": "",
        "status": status_label,
        "metadata": [
            {"label": "Teacher", "value": _str(session.teacher)},
            {"label": "Academic year", "value": _str(session.academic_year)},
            {"label": "Term", "value": _str(session.term)},
            {"label": "Lesson", "value": _str(session.time_slot) or "Not specified"},
        ],
        "metrics": [
            {"label": "Students", "value": len(students), "hint": "Registered in this class stream", "tone": "blue"},
            {"label": "Present", "value": counts[AttendanceStatus.PRESENT], "hint": "Marked present", "tone": "green"},
            {"label": "Absent", "value": counts[AttendanceStatus.ABSENT], "hint": "Marked absent", "tone": "gold"},
            {"label": "Late / excused", "value": counts[AttendanceStatus.LATE] + counts[AttendanceStatus.EXCUSED], "hint": "Other attendance outcomes", "tone": "violet"},
        ],
        "tabs": [
            _tab(
                "roster",
                "Student register",
                [("display_id", "Student ID"), ("student_name", "Student"), ("status", "Status"), ("remarks", "Remarks")],
                students,
                "Record the status of each student. Submitting locks the session and writes an audit entry.",
                "No students are registered in this class stream.",
            ),
        ],
        "actions": [
            {"label": "Back to attendance", "href": _module_path(request, "attendance"), "icon": "calendar-check", "primary": True},
        ],
        "workflow": {
            "kind": "attendance_capture",
            "locked": session.is_locked,
            "can_edit": can_edit,
            "can_unlock": can_unlock,
            "allow_teacher_edit_locked": bool(policy and policy.allow_teacher_edit_locked_sessions),
            "blocked_reason": (
                "This session is locked. An administrator must reopen it before marks can be changed."
                if session.is_locked and not can_unlock and not (policy and policy.allow_teacher_edit_locked_sessions and is_assigned_teacher)
                else ""
            ),
            "statuses": [{"value": value, "label": label} for value, label in AttendanceStatus.choices],
            "students": students,
        },
    }


def perform_entity_action(request, resource: str, pk: int):
    if resource == "attendance":
        return _perform_attendance_action(request, pk)
    if resource != "results" or request.data.get("action") not in {"finalize", "reject"}:
        return {"detail": "This contextual action is not available."}, 404
    if not can_verify_results(request):
        return {"detail": "Your current role cannot verify result batches."}, 403

    from app.services.results_sampling import evaluate_batch_verification, update_sample_mark

    try:
        batch = ResultBatch.objects.select_related("assessment").get(pk=pk)
    except ResultBatch.DoesNotExist:
        return {"detail": "Result batch not found."}, 404
    if batch.status != "PENDING":
        return {"detail": "This batch is no longer pending verification."}, 409
    if batch.submitted_by_id == request.user.id:
        return {"detail": "You cannot verify a batch that you submitted."}, 403

    samples = list(VerificationSample.objects.filter(result__batch=batch).select_related("result", "result__student"))
    if not samples:
        return {"detail": "No verification samples are available for this batch."}, 409

    action = request.data.get("action")
    reason = str(request.data.get("rejection_reason") or "").strip()
    if action == "reject":
        if not reason:
            return {"detail": "Enter a correction reason before flagging this batch."}, 400
        batch.status = "FLAGGED"
        batch.rejection_reason = reason
        batch.verified_by = request.user
        batch.verified_at = timezone.now()
        batch.save(update_fields=["status", "rejection_reason", "verified_by", "verified_at"])
        Result.objects.filter(batch=batch).update(status="FLAGGED")
        from app.services.results_sampling import _create_verification_report
        _create_verification_report(batch, request.user)
        next_batch = ResultBatch.objects.filter(status="PENDING").exclude(pk=batch.pk).order_by("submitted_at", "id").first()
        return {
            "detail": "Batch flagged for correction.",
            "status": batch.status,
            "next_href": _entity_path(request, "results", next_batch.pk, query={"view": "verification"}) if next_batch else "",
        }, 200

    marks = request.data.get("marks") or {}
    for sample in samples:
        raw_value = marks.get(str(sample.pk), marks.get(sample.pk, ""))
        if raw_value in (None, "") and sample.checked_at:
            continue
        if raw_value in (None, ""):
            return {"detail": f"Enter a verifier mark for {sample.result.student}."}, 400
        try:
            mark = Decimal(str(raw_value))
        except (InvalidOperation, TypeError, ValueError):
            return {"detail": f"Enter a valid verifier mark for {sample.result.student}."}, 400
        if mark < 0 or mark > Decimal(str(batch.assessment.out_of)):
            return {"detail": f"Verifier marks must be between 0 and {batch.assessment.out_of}."}, 400
        update_sample_mark(sample, mark, request.user)

    mismatch_count = VerificationSample.objects.filter(result__batch=batch, matched=False).count()
    if mismatch_count and not reason:
        return {"detail": f"{mismatch_count} sample mark(s) differ. Enter a correction reason before finalizing."}, 400
    decision = evaluate_batch_verification(batch, request.user, rejection_reason=reason)
    next_batch = ResultBatch.objects.filter(status="PENDING").exclude(pk=batch.pk).order_by("submitted_at", "id").first()
    return {
        "detail": "Batch verified successfully." if decision == "VERIFIED" else "Differences found; the batch was flagged for correction.",
        "status": decision,
        "next_href": _entity_path(request, "results", next_batch.pk, query={"view": "verification"}) if next_batch else "",
    }, 200


def _perform_attendance_action(request, pk: int):
    from django.db import transaction
    from app.services.attendance import lock_session, save_attendance_records, unlock_session
    from .workspace import _staff_for_user

    action = request.data.get("action")
    if action not in {"save", "submit", "unlock"}:
        return {"detail": "Choose a valid attendance action."}, 400

    role = canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)
    is_admin = bool(request.user.is_superuser or role == "Admin")
    is_manager = role in {"Admin", "Head Teacher", "Director of Studies"}
    staff = _staff_for_user(request.user)
    try:
        session = AttendanceSession.objects.select_related("teacher").get(pk=pk)
    except AttendanceSession.DoesNotExist:
        return {"detail": "Attendance session not found."}, 404

    if role == "Parent":
        return {"detail": "Parent accounts cannot change attendance."}, 403
    if role in {"Teacher", "Class Teacher"} and (not staff or session.teacher_id != staff.pk):
        return {"detail": "You can only change attendance sessions assigned to you."}, 403
    if not (is_manager or role in {"Teacher", "Class Teacher"}):
        return {"detail": "Your current role cannot change attendance."}, 403

    if action == "unlock":
        if not is_admin:
            return {"detail": "Only an administrator can reopen a locked attendance session."}, 403
        if not session.is_locked:
            return {"detail": "This attendance session is already open."}, 409
        reason = str(request.data.get("reason") or "").strip()
        if not reason:
            return {"detail": "Enter a reason before reopening this session."}, 400
        if len(reason) > 255:
            return {"detail": "The reopening reason must be 255 characters or fewer."}, 400
        with transaction.atomic():
            session = AttendanceSession.objects.select_for_update().get(pk=pk)
            if not session.is_locked:
                return {"detail": "This attendance session is already open."}, 409
            unlock_session(session, actor_user=request.user, reason=reason)
        return {"detail": "Attendance session reopened.", "status": "Open"}, 200

    policy = AttendancePolicy.objects.first()
    can_edit_locked = bool(
        role in {"Teacher", "Class Teacher"}
        and staff
        and session.teacher_id == staff.pk
        and policy
        and policy.allow_teacher_edit_locked_sessions
    )
    if session.is_locked and not can_edit_locked:
        return {"detail": "This attendance session is locked. An administrator must reopen it before editing."}, 409

    marks = request.data.get("marks")
    if not isinstance(marks, dict):
        return {"detail": "Attendance marks must be provided as a student-to-status map."}, 400
    registered_ids = set(
        ClassRegister.objects.filter(
            academic_class_stream=session.class_stream,
        ).values_list("student_id", flat=True)
    )
    if not registered_ids:
        return {"detail": "There are no registered students in this class stream."}, 409
    normalized: dict[str, dict[str, str]] = {}
    for raw_student_id, row in marks.items():
        try:
            student_id = int(raw_student_id)
        except (TypeError, ValueError):
            return {"detail": "Attendance contains an invalid student identifier."}, 400
        if student_id not in registered_ids:
            return {"detail": "Attendance includes a student outside this class register."}, 400
        if not isinstance(row, dict):
            return {"detail": "Each attendance mark must include a status and optional remarks."}, 400
        mark_status = row.get("status")
        allowed_statuses = {value for value, _ in AttendanceStatus.choices}
        if mark_status not in allowed_statuses:
            return {"detail": f"Choose a valid attendance status for student {student_id}."}, 400
        remarks = row.get("remarks", "")
        if not isinstance(remarks, str) or len(remarks) > 255:
            return {"detail": f"Remarks for student {student_id} must be 255 characters or fewer."}, 400
        normalized[str(student_id)] = {"status": mark_status, "remarks": remarks.strip()}

    if action == "submit":
        existing = {
            str(row.student_id): row.status
            for row in AttendanceRecord.objects.filter(session=session, student_id__in=registered_ids)
        }
        statuses = {**existing, **{student_id: row["status"] for student_id, row in normalized.items()}}
        if any(statuses.get(str(student_id), AttendanceStatus.UNMARKED) == AttendanceStatus.UNMARKED for student_id in registered_ids):
            return {"detail": "Mark every student before submitting attendance."}, 400
    elif action != "save":
        return {"detail": "Choose a valid attendance action."}, 400

    with transaction.atomic():
        session = AttendanceSession.objects.select_for_update().get(pk=pk)
        if session.is_locked and not can_edit_locked:
            return {"detail": "This attendance session was locked before your changes could be saved."}, 409
        save_attendance_records(
            session,
            normalized,
            captured_by=session.teacher,
            actor_user=request.user,
        )
        if action == "submit":
            lock_session(session, actor_user=request.user)

    return {
        "detail": "Attendance saved." if action == "save" else "Attendance submitted and locked.",
        "status": "Open" if action == "save" else "Locked",
    }, 200
