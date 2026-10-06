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
from .marks_workspace import MarksEntryAPIView, MarksHubAPIView
from .parent_workspace import ParentWorkspaceAPIView

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
    path("workspace/bootstrap/", WorkspaceBootstrapAPIView.as_view(), name="api_workspace_bootstrap"),
    path("workspace/dashboard/", WorkspaceDashboardAPIView.as_view(), name="api_workspace_dashboard"),
    path("workspace/search/", WorkspaceSearchAPIView.as_view(), name="api_workspace_search"),
    path("workspace/results/marks/", MarksHubAPIView.as_view(), name="api_workspace_marks_hub"),
    path("workspace/results/marks/<int:assessment_id>/", MarksEntryAPIView.as_view(), name="api_workspace_marks_entry"),
    path("workspace/resources/<str:resource>/", WorkspaceResourceAPIView.as_view(), name="api_workspace_resource"),
    path("workspace/resources/<str:resource>/form/", WorkspaceResourceFormAPIView.as_view(), name="api_workspace_resource_create_form"),
    path("workspace/resources/<str:resource>/<int:pk>/form/", WorkspaceResourceFormAPIView.as_view(), name="api_workspace_resource_edit_form"),
    path("workspace/resources/<str:resource>/<int:pk>/action/", WorkspaceEntityActionAPIView.as_view(), name="api_workspace_entity_action"),
    path("workspace/resources/<str:resource>/<int:pk>/", WorkspaceEntityAPIView.as_view(), name="api_workspace_entity"),
    path("auth/login/", LoginAPIView.as_view(), name="api_auth_login"),
    path("auth/me/", CurrentUserAPIView.as_view(), name="api_auth_me"),
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
