from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import AuditLog, Role, Staff, StaffAccount


class WorkspaceNavigationTests(APITestCase):
    """Keep the task-oriented sidebar and its finance blind spot covered."""

    def _user_for_role(self, role_name: str):
        suffix = role_name.lower().replace(" ", "-")
        role, _ = Role.objects.get_or_create(name=role_name)
        staff = Staff.objects.create(
            first_name=role_name[:20],
            last_name="Workspace",
            birth_date=date(1990, 1, 1),
            gender="F",
            address="Kampala",
            marital_status="U",
            contacts=f"0700{len(role_name):06d}",
            email=f"{suffix}@example.test",
            qualification="Degree",
            nin_no=f"NAV{len(role_name):011d}",
            hire_date=date(2020, 1, 1),
            department="Academic",
            salary="1.00",
            staff_status="Active",
        )
        user = get_user_model().objects.create_user(
            username=f"{suffix}-workspace",
            password="A-strong-test-password-123",
        )
        StaffAccount.objects.create(staff=staff, user=user, role=role)
        return user

    def test_bursar_sees_flat_finance_and_communication_sections(self):
        self.client.force_authenticate(user=self._user_for_role("Bursar"))

        response = self.client.get(reverse("api_workspace_bootstrap"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        groups = {group["key"]: group for group in response.data["navigation"]}
        self.assertIn("control_tower", groups)
        self.assertIn("administration", groups)
        self.assertIn("finance", groups)
        self.assertIn("communication", groups)
        self.assertEqual(
            [item["slug"] for item in groups["finance"]["items"]],
            ["fees", "finance"],
        )

    def test_admin_gets_consolidated_enterprise_navigation(self):
        admin = get_user_model().objects.create_superuser(
            username="navigation-admin",
            email="navigation-admin@example.test",
            password="A-strong-test-password-123",
        )
        self.client.force_authenticate(user=admin)

        response = self.client.get(reverse("api_workspace_bootstrap"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        groups = response.data["navigation"]
        self.assertEqual(
            [group["key"] for group in groups],
            ["control_tower", "administration", "academics", "finance", "communication"],
        )
        self.assertEqual(
            [item["label"] for item in groups[1]["items"]],
            ["Admissions", "Student Directory", "Staff & Roles", "System Administration"],
        )
        self.assertEqual(
            [item["label"] for item in groups[2]["items"]],
            ["Academic Setup", "Timetable", "Attendance", "Assessments & Results", "Library"],
        )

    def test_class_teacher_gets_a_focused_classroom_navigation(self):
        self.client.force_authenticate(user=self._user_for_role("Class Teacher"))

        response = self.client.get(reverse("api_workspace_bootstrap"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        groups = response.data["navigation"]
        self.assertEqual(
            [group["key"] for group in groups],
            ["classroom", "teaching", "learners", "communication"],
        )
        self.assertEqual(
            [item["slug"] for item in groups[0]["items"]],
            ["overview", "my-class"],
        )
        self.assertEqual(
            [item["slug"] for item in groups[1]["items"]],
            ["attendance", "results", "timetable"],
        )

    def test_teacher_and_dos_are_denied_finance_in_navigation_and_api(self):
        for role_name in ("Teacher", "Director of Studies"):
            with self.subTest(role=role_name):
                user = self._user_for_role(role_name)
                self.client.force_authenticate(user=user)

                bootstrap = self.client.get(reverse("api_workspace_bootstrap"))
                self.assertEqual(bootstrap.status_code, status.HTTP_200_OK)
                self.assertNotIn(
                    "finance",
                    [group["key"] for group in bootstrap.data["navigation"]],
                )

                finance = self.client.get(
                    reverse("api_workspace_resource", kwargs={"resource": "finance"}),
                )
                self.assertEqual(finance.status_code, status.HTTP_403_FORBIDDEN)
                direct_read = self.client.get(
                    reverse("api_workspace_student_finance", kwargs={"screen": "accounts"}),
                )
                direct_write = self.client.post(
                    reverse("api_workspace_student_finance_record", kwargs={"screen": "account", "pk": 1}),
                    {"action": "record_payment"},
                    format="json",
                )
                self.assertEqual(direct_read.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(direct_write.status_code, status.HTTP_403_FORBIDDEN)

                audits = list(AuditLog.objects.filter(user=user).order_by("id"))
                self.assertEqual(len(audits), 3)
                self.assertTrue(all(audit.object_repr == "Denied finance access" for audit in audits))
                self.assertTrue(all(audit.extra["security_event"] == "finance_access_denied" for audit in audits))
                self.assertEqual(
                    {audit.extra["operation"] for audit in audits},
                    {"list", "student_finance_read", "student_finance_write"},
                )
