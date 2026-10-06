from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .workspace import (
    WorkspaceBootstrapAPIView,
    WorkspaceDashboardAPIView,
    WorkspaceEntityActionAPIView,
    WorkspaceEntityAPIView,
    WorkspaceResourceAPIView,
    WorkspaceResourceFormAPIView,
    WorkspaceSearchAPIView,
)
from .academic_workspace import AcademicToolAPIView
from .classes_workspace import ClassesWorkspaceAPIView
from .admissions_workspace import AdmissionsWorkspaceAPIView
from .attendance_workspace import AttendanceWorkspaceAPIView
from .auth_workspace import RoleSwitchAPIView
from .communication_workspace import CommunicationConsoleAPIView
from .finance_operations import FinanceOperationsAPIView
from .library_workspace import LibraryConsoleAPIView
from .marks_workspace import MarksEntryAPIView, MarksHubAPIView
from .parent_access_management import ParentAccessManagementAPIView
from .parent_workspace import ParentWorkspaceAPIView
from .results_operations import ResultsOperationsAPIView
from .student_finance import StudentFinanceAPIView
from .timetable_operations import TimetableOperationsAPIView
from .user_management import UserRolesWorkspaceAPIView

from .views import (
    CurrentUserAPIView,
    DashboardSummaryAPIView,
    FeeLedgerAPIView,
    GradeMatrixAPIView,
    LoginAPIView,
    PasswordChangeAPIView,
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
    StudentDetailAPIView,
    StudentListAPIView,
    UserListAPIView,
)

urlpatterns = [
    path("workspace/parent/<str:action>/", ParentWorkspaceAPIView.as_view(), name="api_workspace_parent"),
    path("workspace/parent-access/", ParentAccessManagementAPIView.as_view(), name="api_workspace_parent_access"),
    path("workspace/bootstrap/", WorkspaceBootstrapAPIView.as_view(), name="api_workspace_bootstrap"),
    path("workspace/dashboard/", WorkspaceDashboardAPIView.as_view(), name="api_workspace_dashboard"),
    path("workspace/search/", WorkspaceSearchAPIView.as_view(), name="api_workspace_search"),
    path("workspace/users-roles/", UserRolesWorkspaceAPIView.as_view(), name="api_workspace_users_roles"),
    path("workspace/users-roles/<int:user_id>/", UserRolesWorkspaceAPIView.as_view(), name="api_workspace_users_roles_record"),
    path("workspace/academics/<str:tool>/", AcademicToolAPIView.as_view(), name="api_workspace_academic_tool"),
    path("workspace/academics/<str:tool>/<int:pk>/", AcademicToolAPIView.as_view(), name="api_workspace_academic_tool_record"),
    path("workspace/classes/<int:pk>/<str:action>/", ClassesWorkspaceAPIView.as_view(), name="api_workspace_classes_action"),
    path("workspace/admissions/<str:screen>/", AdmissionsWorkspaceAPIView.as_view(), name="api_workspace_admissions"),
    path("workspace/admissions/<str:screen>/<int:pk>/", AdmissionsWorkspaceAPIView.as_view(), name="api_workspace_admissions_record"),
    path("workspace/attendance-console/<str:screen>/", AttendanceWorkspaceAPIView.as_view(), name="api_workspace_attendance_console"),
    path("workspace/student-finance/<str:screen>/", StudentFinanceAPIView.as_view(), name="api_workspace_student_finance"),
    path("workspace/student-finance/<str:screen>/<int:pk>/", StudentFinanceAPIView.as_view(), name="api_workspace_student_finance_record"),
    path("workspace/finance-console/<str:screen>/", FinanceOperationsAPIView.as_view(), name="api_workspace_finance_console"),
    path("workspace/communication-console/<str:screen>/", CommunicationConsoleAPIView.as_view(), name="api_workspace_communication_console"),
    path("workspace/communication-console/<str:screen>/<int:pk>/", CommunicationConsoleAPIView.as_view(), name="api_workspace_communication_console_record"),
    path("workspace/library-console/<str:screen>/", LibraryConsoleAPIView.as_view(), name="api_workspace_library_console"),
    path("workspace/library-console/<str:screen>/<int:pk>/", LibraryConsoleAPIView.as_view(), name="api_workspace_library_console_record"),
    path("workspace/results/operations/<str:screen>/", ResultsOperationsAPIView.as_view(), name="api_workspace_results_operations"),
    path("workspace/results/marks/", MarksHubAPIView.as_view(), name="api_workspace_marks_hub"),
    path("workspace/results/marks/<int:assessment_id>/", MarksEntryAPIView.as_view(), name="api_workspace_marks_entry"),
    path("workspace/timetable-console/<str:screen>/", TimetableOperationsAPIView.as_view(), name="api_workspace_timetable_console"),
    path("workspace/resources/<str:resource>/", WorkspaceResourceAPIView.as_view(), name="api_workspace_resource"),
    path("workspace/resources/<str:resource>/form/", WorkspaceResourceFormAPIView.as_view(), name="api_workspace_resource_create_form"),
    path("workspace/resources/<str:resource>/<int:pk>/form/", WorkspaceResourceFormAPIView.as_view(), name="api_workspace_resource_edit_form"),
    path("workspace/resources/<str:resource>/<int:pk>/action/", WorkspaceEntityActionAPIView.as_view(), name="api_workspace_entity_action"),
    path("workspace/resources/<str:resource>/<int:pk>/", WorkspaceEntityAPIView.as_view(), name="api_workspace_entity"),
    path("auth/login/", LoginAPIView.as_view(), name="api_auth_login"),
    path("auth/me/", CurrentUserAPIView.as_view(), name="api_auth_me"),
    path("auth/switch-role/", RoleSwitchAPIView.as_view(), name="api_auth_switch_role"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="api_auth_refresh"),
    path("auth/password/change/", PasswordChangeAPIView.as_view(), name="api_auth_password_change"),
    path("auth/password/reset/", PasswordResetRequestAPIView.as_view(), name="api_auth_password_reset"),
    path("auth/password/reset/confirm/", PasswordResetConfirmAPIView.as_view(), name="api_auth_password_reset_confirm"),
    path("users/", UserListAPIView.as_view(), name="api_users"),
    path("students/", StudentListAPIView.as_view(), name="api_students"),
    path("students/<int:pk>/", StudentDetailAPIView.as_view(), name="api_student_detail"),
    path("grades/", GradeMatrixAPIView.as_view(), name="api_grades"),
    path("fees/", FeeLedgerAPIView.as_view(), name="api_fee_ledger"),
    path("dashboard-summary/", DashboardSummaryAPIView.as_view(), name="api_dashboard_summary"),
]
