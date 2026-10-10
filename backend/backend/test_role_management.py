from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import AuditLog, Role, RolePermission, Staff, StaffAccount


class RoleManagementTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="role-admin",
            email="role-admin@example.test",
            password="A-strong-test-password-123",
        )
        self.teacher, _ = Role.objects.get_or_create(name="Teacher")
        self.client.force_authenticate(user=self.admin)

    def _staff_user_for(self, role: Role):
        staff = Staff.objects.create(
            first_name="Custom",
            last_name="Role",
            birth_date=date(1990, 1, 1),
            gender="F",
            address="Kampala",
            marital_status="U",
            contacts="0700000000",
            email="custom-role@example.test",
            qualification="Degree",
            nin_no="NAV00000000001",
            hire_date=date(2020, 1, 1),
            department="Academic",
            salary="1.00",
            staff_status="Active",
        )
        staff.roles.add(role)
        user = get_user_model().objects.create_user(
            username="custom-role-user",
            password="A-strong-test-password-123",
        )
        StaffAccount.objects.create(staff=staff, user=user, role=role)
        return user

    def test_admin_can_create_role_from_template_and_save_module_access(self):
        created = self.client.post(
            reverse("api_workspace_roles"),
            {"name": "Transport Coordinator", "description": "Coordinates school transport.", "template_id": self.teacher.pk},
            format="json",
        )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        role_id = created.data["role"]["id"]
        role = Role.objects.get(pk=role_id)
        self.assertFalse(role.is_system)
        self.assertTrue(RolePermission.objects.filter(role=role, module="students", allowed=True).exists())

        access = {row.module: False for row in RolePermission.objects.filter(role=role)}
        access["communication"] = True
        saved = self.client.patch(
            reverse("api_workspace_role_record", kwargs={"role_id": role.pk}),
            {"action": "permissions", "access": access},
            format="json",
        )

        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        self.assertTrue(RolePermission.objects.get(role=role, module="communication").allowed)
        self.assertFalse(RolePermission.objects.get(role=role, module="students").allowed)
        self.assertTrue(AuditLog.objects.filter(
            user=self.admin,
            object_repr="Role permissions saved: Transport Coordinator",
        ).exists())

    def test_saved_module_access_is_enforced_for_a_custom_role(self):
        created = self.client.post(
            reverse("api_workspace_roles"),
            {"name": "Reception", "template_id": self.teacher.pk},
            format="json",
        )
        role = Role.objects.get(pk=created.data["role"]["id"])
        access = {row.module: False for row in RolePermission.objects.filter(role=role)}
        access["communication"] = True
        self.client.patch(
            reverse("api_workspace_role_record", kwargs={"role_id": role.pk}),
            {"action": "permissions", "access": access},
            format="json",
        )
        user = self._staff_user_for(role)
        self.client.force_authenticate(user=user)

        denied = self.client.get(reverse("api_workspace_resource", kwargs={"resource": "students"}))
        allowed = self.client.get(reverse("api_workspace_resource", kwargs={"resource": "communication"}))

        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

    def test_system_roles_are_protected_from_deletion(self):
        admin_role = Role.objects.get(name="Admin")

        response = self.client.delete(
            reverse("api_workspace_role_record", kwargs={"role_id": admin_role.pk}),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Role.objects.filter(pk=admin_role.pk).exists())
