"""Shared module-access definitions for the role management workspace.

The module registry is deliberately small and server-side.  A browser may edit
which module groups a role can enter, but the server always expands those
groups to the underlying workspace resources before authorising a request.
"""

from __future__ import annotations


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
    "Class Teacher": {"students", "classes", "subjects", "results", "attendance", "timetable", "communication", "my-class"},
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


# ``my-class`` remains a Class Teacher-only workspace even though the Classes
# module is visible to other teaching roles.  It is intentionally not added to
# the Classes group below.
PERMISSION_MODULES = (
    ("students", "Students", frozenset({"students"})),
    ("staff", "Staff", frozenset({"staff"})),
    ("admissions", "Admissions", frozenset({"admissions"})),
    ("parents", "Parent access", frozenset({"parents"})),
    ("classes", "Classes", frozenset({"classes"})),
    ("subjects", "Subjects", frozenset({"subjects"})),
    ("results", "Results", frozenset({"results"})),
    ("attendance", "Attendance", frozenset({"attendance"})),
    ("timetable", "Timetable", frozenset({"timetable"})),
    ("fees", "Fees & payments", frozenset({"fees", "fees-payments", "fees-class-bills", "fees-bill-items"})),
    ("finance", "Finance", frozenset({"finance", "finance-budgets", "finance-budget-items", "finance-expenditure-items", "finance-expenses", "finance-vendors", "finance-income"})),
    ("library", "Library", frozenset({"library"})),
    ("communication", "Communication", frozenset({"communication"})),
    ("audit", "Audit", frozenset({"audit"})),
    ("settings", "Settings", frozenset({"settings"})),
)

PERMISSION_MODULE_KEYS = frozenset(key for key, _label, _resources in PERMISSION_MODULES)


def default_module_access(role_label: str) -> dict[str, bool]:
    """Return the module access represented by the legacy built-in role map."""
    allowed = ROLE_RESOURCES.get(role_label, set())
    return {
        key: bool("*" in allowed or allowed.intersection(resources))
        for key, _label, resources in PERMISSION_MODULES
    }


def resources_for_modules(module_keys) -> set[str]:
    selected = set(module_keys)
    resources: set[str] = set()
    for key, _label, module_resources in PERMISSION_MODULES:
        if key in selected:
            resources.update(module_resources)
    return resources
