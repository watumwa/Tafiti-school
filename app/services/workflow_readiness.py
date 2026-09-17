"""Fast, shared prerequisite guidance for the operational modules.

This layer is advisory. Existing view/model validation remains the authority for
mutations, while this service tells users what must be configured before they
reach a dead end.
"""

from django.core.cache import cache
from django.urls import NoReverseMatch, reverse

from app.models import (
    AcademicClass,
    AcademicClassStream,
    Assessment,
    AssessmentType,
    BillItem,
    Budget,
    Class,
    ClassBill,
    ClassRegister,
    ClassSubjectAllocation,
    GradingSystem,
    IncomeSource,
    Result,
    ResultBatch,
    Staff,
    StaffAccount,
    Student,
    Subject,
    Term,
    TimeSlot,
    Timetable,
    Vendor,
)
from app.selectors.school_settings import get_current_academic_year


CACHE_SECONDS = 45


def _url(name):
    try:
        return reverse(name)
    except NoReverseMatch:
        return ""


def _step(key, module, task, description, url_name, missing=None, ready_label="Ready"):
    missing = [item for item in (missing or []) if item]
    return {
        "key": key,
        "module": module,
        "task": task,
        "description": description,
        "url": _url(url_name),
        "missing": missing,
        "is_ready": not missing,
        "status": ready_label if not missing else "Action required",
        "severity": "success" if not missing else "warning",
    }


def build_readiness_catalog():
    current_year = get_current_academic_year()
    current_term = (
        Term.objects.filter(is_current=True, academic_year=current_year).first()
        if current_year
        else None
    )
    cache_key = f"workflow-readiness:v3:{getattr(current_year, 'id', 0)}:{getattr(current_term, 'id', 0)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    has_classes = Class.objects.exists()
    has_streams = AcademicClassStream.objects.exists()
    period_classes = AcademicClass.objects.filter(
        academic_year=current_year,
        term=current_term,
    ) if current_year and current_term else AcademicClass.objects.none()
    period_streams = AcademicClassStream.objects.filter(
        academic_class__in=period_classes,
    )
    period_registers = ClassRegister.objects.filter(
        academic_class_stream__in=period_streams,
        student__is_active=True,
    )
    period_allocations = ClassSubjectAllocation.objects.filter(
        academic_class_stream__in=period_streams,
        is_active=True,
    )
    period_timetable = Timetable.objects.filter(class_stream__in=period_streams)
    period_assessments = Assessment.objects.filter(academic_class__in=period_classes)

    period_missing = []
    if not current_year:
        period_missing.append("Set the current academic year")
    if current_year and not current_term:
        period_missing.append("Set the current term for the academic year")

    steps = []
    steps.append(_step(
        "academic_period", "Academic setup", "Set the active academic period",
        "Every operational module uses this period by default.", "settings_page",
        period_missing,
    ))
    steps.append(_step(
        "class_structure", "Academic setup", "Create classes and current-term streams",
        "Learners, subjects, timetables and reports require a class structure.", "academic_class_page",
        [
            None if has_classes else "Create at least one class",
            None if period_missing else (None if period_classes.exists() else "Create academic classes for the current term"),
            None if period_missing else (None if period_streams.exists() else "Add streams to the current-term classes"),
        ],
    ))
    steps.append(_step(
        "staffing", "Staff", "Create staff and user accounts",
        "Teachers and approvers need linked staff accounts and roles.", "staff_page",
        [
            None if Staff.objects.exists() else "Create staff profiles",
            None if StaffAccount.objects.exists() else "Create staff login accounts",
        ],
    ))
    steps.append(_step(
        "learners", "Students", "Register learners into current-term streams",
        "Attendance, billing, marks and reports use the class register.", "student_page",
        [
            None if Student.objects.filter(is_active=True).exists() else "Create active learner records",
            None if period_missing else (None if period_registers.exists() else "Register learners in current-term class streams"),
        ],
    ))
    steps.append(_step(
        "subject_allocations", "Subjects", "Allocate subjects and teachers",
        "Timetables and assessment entry use active subject allocations.", "subject_allocation_page",
        [
            None if Subject.objects.exists() else "Create subjects",
            None if period_missing else (None if period_allocations.exists() else "Allocate current-term subjects to teachers and streams"),
        ],
    ))
    steps.append(_step(
        "timetable", "Timetable", "Build the teaching timetable",
        "Attendance sessions depend on configured periods and scheduled lessons.", "school_timetable",
        [
            None if TimeSlot.objects.exists() else "Configure timetable periods",
            None if period_allocations.exists() else "Complete subject allocations first",
            None if period_missing else (None if period_timetable.exists() else "Create the current-term timetable"),
        ],
    ))
    steps.append(_step(
        "attendance", "Attendance", "Take learner attendance",
        "Learners must be registered and lessons scheduled before attendance.", "attendance_dashboard",
        [
            None if period_registers.exists() else "Register learners in class streams",
            None if period_timetable.exists() else "Create the teaching timetable",
        ],
    ))
    steps.append(_step(
        "assessments", "Assessments", "Create assessment structures",
        "Assessment types, grading and subject allocations must exist first.", "assessment_create",
        [
            None if AssessmentType.objects.exists() else "Create assessment types and weights",
            None if GradingSystem.objects.exists() else "Configure the grading system",
            None if period_allocations.exists() else "Complete current-term subject allocations",
            None if period_missing else (None if period_assessments.exists() else "Create current-term assessments"),
        ],
    ))
    steps.append(_step(
        "marks", "Results", "Enter and submit marks",
        "Only created assessments with registered learners can receive marks.", "add_results_page",
        [
            None if period_registers.exists() else "Register learners in the current term",
            None if period_assessments.exists() else "Create assessments first",
        ],
    ))
    steps.append(_step(
        "verification", "Results", "Verify submitted result batches",
        "Teachers must complete and submit marks before DOS verification.", "verification_overview",
        [
            None if ResultBatch.objects.filter(assessment__in=period_assessments, status__in=["PENDING", "VERIFIED", "FLAGGED"]).exists()
            else "Submit at least one completed mark batch for verification",
        ],
    ))
    steps.append(_step(
        "reports", "Reports", "Prepare and approve report cards",
        "Official reports require verified marks and report remarks.", "class_assessment_combined",
        [
            None if Result.objects.filter(assessment__in=period_assessments, status="VERIFIED").exists()
            else "Verify current-term results before generating official reports",
        ],
    ))
    steps.append(_step(
        "fees", "Fees", "Configure charges and create student bills",
        "Bills require enrolled learners, bill items and a class billing structure.", "class_bill_list",
        [
            None if period_registers.exists() else "Register learners in the current term",
            None if BillItem.objects.exists() else "Create bill items",
            None if ClassBill.objects.filter(academic_class__in=period_classes).exists() else "Configure current-term class bills",
        ],
    ))
    steps.append(_step(
        "finance", "Finance", "Configure finance master data",
        "Budgets, vendors and income sources support controlled transactions and reports.", "financial_dashboard",
        [
            None if IncomeSource.objects.exists() else "Create an income source",
            None if Vendor.objects.exists() else "Create vendors for expenditure processing",
            None if Budget.objects.exists() else "Create a budget before budget monitoring",
        ],
    ))
    steps.append(_step(
        "communications", "Communications", "Prepare recipients before messaging",
        "Announcements and messages require active staff accounts.", "announcement_list",
        [None if StaffAccount.objects.exists() else "Create staff login accounts and roles"],
    ))
    steps.append(_step(
        "promotion", "Promotion", "Prepare destination classes before promotion",
        "Promotion requires registered learners and academic classes in another period.", "student_promotion_workflow",
        [
            None if period_registers.exists() else "Register learners in the source term",
            None if AcademicClass.objects.exclude(academic_year=current_year, term=current_term).exists()
            else "Create destination academic classes before promotion",
        ],
    ))

    cache.set(cache_key, steps, CACHE_SECONDS)
    return steps


URL_MODULE_MAP = {
    "settings": {"academic_period"},
    "section": {"class_structure"},
    "department": {"staffing"},
    "signature": {"reports"},
    "user": {"staffing"},
    "academic": {"academic_period", "class_structure"},
    "class": {"academic_period", "class_structure"},
    "stream": {"class_structure"},
    "student": {"academic_period", "class_structure", "learners"},
    "register": {"class_structure", "learners"},
    "staff": {"staffing"},
    "subject": {"academic_period", "class_structure", "staffing", "subject_allocations"},
    "timetable": {"academic_period", "class_structure", "subject_allocations", "timetable"},
    "attendance": {"academic_period", "learners", "timetable", "attendance"},
    "assessment": {"academic_period", "learners", "subject_allocations", "assessments"},
    "result": {"academic_period", "learners", "assessments", "marks", "verification"},
    "verification": {"marks", "verification"},
    "report": {"verification", "reports"},
    "fee": {"academic_period", "learners", "fees"},
    "bill": {"academic_period", "learners", "fees"},
    "payment": {"fees"},
    "finance": {"finance"},
    "income": {"finance"},
    "expense": {"finance"},
    "expenditure": {"finance"},
    "vendor": {"finance"},
    "budget": {"finance"},
    "announcement": {"communications"},
    "event": {"communications"},
    "message": {"communications"},
    "promotion": {"academic_period", "class_structure", "learners", "promotion"},
}


def readiness_for_request(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"workflow_steps": [], "workflow_page_notices": [], "workflow_action_count": 0}

    all_steps = build_readiness_catalog()
    role_name = (request.session.get("active_role_name") or "").strip().lower()
    if not role_name:
        account = getattr(request.user, "staff_account", None)
        role_name = (getattr(getattr(account, "role", None), "name", "") or "").strip().lower()

    all_keys = {step["key"] for step in all_steps}
    academic_keys = {
        "academic_period", "class_structure", "staffing", "learners", "subject_allocations",
        "timetable", "attendance", "assessments", "marks", "verification", "reports",
        "communications", "promotion",
    }
    teacher_keys = {
        "academic_period", "class_structure", "learners", "subject_allocations", "timetable",
        "attendance", "assessments", "marks", "verification", "reports", "communications",
    }
    finance_keys = {"academic_period", "class_structure", "learners", "fees", "finance", "communications"}
    if request.user.is_superuser or role_name in {"admin", "head master", "headmaster", "head teacher", "headteacher"}:
        visible_keys = all_keys
    elif role_name in {"director of studies", "dos"}:
        visible_keys = academic_keys
    elif role_name in {"teacher", "class teacher", "class_teacher"}:
        visible_keys = teacher_keys
    elif role_name in {"bursar", "finance"}:
        visible_keys = finance_keys
    else:
        visible_keys = {"academic_period", "communications"}

    steps = [dict(step) for step in all_steps if step["key"] in visible_keys]

    # Keep prerequisite visibility for ordinary users, but do not send them to
    # configuration pages they are not authorized to change.
    configuration_keys = {"academic_period", "class_structure", "staffing", "subject_allocations", "assessments", "fees", "finance", "promotion"}
    if request.user.is_superuser or role_name in {"admin", "head master", "headmaster", "head teacher", "headteacher"}:
        permitted_configuration = configuration_keys
    elif role_name in {"director of studies", "dos"}:
        permitted_configuration = configuration_keys - {"fees", "finance"}
    elif role_name in {"bursar", "finance"}:
        permitted_configuration = {"fees", "finance"}
    else:
        permitted_configuration = set()
    if not request.user.is_superuser:
        for step in steps:
            if step["key"] in configuration_keys - permitted_configuration and not step["is_ready"]:
                step["url"] = ""
                step["missing"] = [f"{item} — contact the responsible administrator" for item in step["missing"]]
    url_name = (getattr(getattr(request, "resolver_match", None), "url_name", None) or "").lower()
    relevant_keys = set()
    for token, keys in URL_MODULE_MAP.items():
        if token in url_name:
            relevant_keys.update(keys)

    page_notices = [step for step in steps if step["key"] in relevant_keys and not step["is_ready"]]
    return {
        "workflow_steps": steps,
        "workflow_page_notices": page_notices[:4],
        "workflow_action_count": sum(1 for step in steps if not step["is_ready"]),
    }
