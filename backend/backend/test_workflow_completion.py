from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import (
    AcademicClass,
    AcademicClassStream,
    AcademicYear,
    Class,
    ClassRegister,
    ParentAccess,
    Payment,
    Section,
    Staff,
    Student,
    StudentBill,
    Stream,
    Term,
)
from app.models.finance import BankAccount, BankStatement, BankTransaction
from backend.workspace import ROLE_RESOURCES


User = get_user_model()


class WorkflowCompletionFixture(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="workflow-admin",
            email="workflow-admin@example.test",
            password="A-strong-test-password-123",
        )
        self.client.force_authenticate(user=self.admin)
        self.year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        self.term = Term.objects.create(
            academic_year=self.year,
            term="1",
            start_date=date(2026, 1, 5),
            end_date=date(2026, 4, 30),
            is_current=True,
        )
        self.section = Section.objects.create(section_name="Workflow Completion")
        self.base_class = Class.objects.create(name="Primary 6", code="P6-WF", section=self.section)
        self.stream = Stream.objects.create(stream="Blue-WF")
        self.teacher = Staff.objects.create(
            first_name="Workflow",
            last_name="Teacher",
            birth_date=date(1990, 1, 1),
            gender="M",
            address="School",
            marital_status="S",
            contacts="0700111222",
            email="workflow-teacher@example.test",
            qualification="Diploma",
            hire_date=date(2020, 1, 1),
            department="Academic",
            salary=1,
            staff_status="Active",
            staff_photo="Staff/Profile_pics/workflow-teacher.jpg",
        )
        self.academic_class = AcademicClass.objects.create(
            section=self.section,
            Class=self.base_class,
            academic_year=self.year,
            term=self.term,
            fees_amount=Decimal("500000.00"),
        )
        self.class_stream = AcademicClassStream.objects.create(
            academic_class=self.academic_class,
            stream=self.stream,
            class_teacher=self.teacher,
        )
        self.student = Student.objects.create(
            reg_no="WF-2026-001",
            student_name="Workflow Student",
            gender="F",
            birthdate=date(2015, 2, 1),
            nationality="Ugandan",
            religion="Muslim",
            address="Kampala",
            guardian="Workflow Guardian",
            relationship="Parent",
            contact="0700123456",
            academic_year=self.year,
            current_class=self.base_class,
            stream=self.stream,
            term=self.term,
        )
        ClassRegister.objects.create(academic_class_stream=self.class_stream, student=self.student)
        self.bill = StudentBill.objects.get(student=self.student, academic_class=self.academic_class)


class FinanceOperationsTests(WorkflowCompletionFixture):
    def test_reconciliation_matches_and_unmatches_equal_payment(self):
        payment = Payment.objects.create(
            bill=self.bill,
            payment_date=date(2026, 10, 6),
            amount=Decimal("125000.00"),
            payment_method="Bank",
            fee_category="Tuition",
            reference_no="WF-PAY-001",
            recorded_by=self.admin.username,
        )
        account = BankAccount.objects.create(
            bank_name="Workflow Bank",
            account_number="WF-ACCOUNT-001",
            account_name="Workflow School",
            account_type="School",
            balance=0,
        )
        statement = BankStatement.objects.create(
            bank_account=account,
            statement_date=date(2026, 10, 6),
            opening_balance=Decimal("0.00"),
            closing_balance=Decimal("125000.00"),
        )
        bank_tx = BankTransaction.objects.create(
            bank_statement=statement,
            transaction_date=date(2026, 10, 6),
            description="School fees deposit",
            amount=Decimal("125000.00"),
            transaction_type="Credit",
            reference="WF-BANK-001",
        )

        url = reverse("api_workspace_finance_console", kwargs={"screen": "reconciliation"})
        overview = self.client.get(url)
        self.assertEqual(overview.status_code, status.HTTP_200_OK)
        self.assertEqual(overview.data["metrics"]["unmatched_bank"], 1)
        self.assertEqual(overview.data["metrics"]["unmatched_payments"], 1)

        matched = self.client.post(
            url,
            {"action": "match", "transaction_id": bank_tx.pk, "payment_id": payment.pk},
            format="json",
        )
        self.assertEqual(matched.status_code, status.HTTP_200_OK, matched.data)
        bank_tx.refresh_from_db()
        self.assertTrue(bank_tx.reconciled)
        self.assertEqual(bank_tx.reconciled_with_id, payment.pk)
        self.assertIsNotNone(bank_tx.reconciliation_date)

        unmatched = self.client.post(
            url,
            {"action": "unmatch", "transaction_id": bank_tx.pk},
            format="json",
        )
        self.assertEqual(unmatched.status_code, status.HTTP_200_OK, unmatched.data)
        bank_tx.refresh_from_db()
        self.assertFalse(bank_tx.reconciled)
        self.assertIsNone(bank_tx.reconciled_with_id)

    def test_reconciliation_rejects_amount_mismatch(self):
        payment = Payment.objects.create(
            bill=self.bill,
            payment_date=date(2026, 10, 6),
            amount=Decimal("100000.00"),
            payment_method="Bank",
            reference_no="WF-PAY-002",
            recorded_by=self.admin.username,
        )
        account = BankAccount.objects.create(
            bank_name="Workflow Bank 2",
            account_number="WF-ACCOUNT-002",
            account_name="Workflow School",
            account_type="School",
            balance=0,
        )
        statement = BankStatement.objects.create(
            bank_account=account,
            statement_date=date(2026, 10, 6),
            opening_balance=0,
            closing_balance=90000,
        )
        bank_tx = BankTransaction.objects.create(
            bank_statement=statement,
            transaction_date=date(2026, 10, 6),
            description="Different amount",
            amount=Decimal("90000.00"),
            transaction_type="Credit",
        )
        response = self.client.post(
            reverse("api_workspace_finance_console", kwargs={"screen": "reconciliation"}),
            {"action": "match", "transaction_id": bank_tx.pk, "payment_id": payment.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        bank_tx.refresh_from_db()
        self.assertFalse(bank_tx.reconciled)

    def test_billing_sync_repairs_missing_student_bill(self):
        StudentBill.objects.filter(pk=self.bill.pk).delete()
        self.assertFalse(StudentBill.objects.filter(student=self.student, academic_class=self.academic_class).exists())

        response = self.client.post(
            reverse("api_workspace_finance_console", kwargs={"screen": "billing"}),
            {"academic_class_id": self.academic_class.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        repaired = StudentBill.objects.get(student=self.student, academic_class=self.academic_class)
        self.assertGreater(repaired.items.count(), 0)
        self.assertEqual(response.data["summary"]["created_bills"], 1)


class ParentAccessLifecycleTests(WorkflowCompletionFixture):
    def test_parent_access_activation_permissions_reset_and_deactivation(self):
        url = reverse("api_workspace_parent_access")
        activated = self.client.post(url, {"action": "activate", "student_id": self.student.pk}, format="json")
        self.assertEqual(activated.status_code, status.HTTP_201_CREATED, activated.data)
        credential = activated.data["credential"]
        self.assertTrue(credential["temporary_password"])
        self.assertNotEqual(credential["temporary_password"], "123")

        access = ParentAccess.objects.select_related("user").get(student=self.student)
        self.assertTrue(access.user.check_password(credential["temporary_password"]))
        self.assertFalse(hasattr(ParentAccess.objects.get(pk=access.pk), "temporary_password"))

        permissions = self.client.post(
            url,
            {
                "action": "permissions",
                "access_id": access.pk,
                "academics": True,
                "finance": False,
                "attendance": True,
            },
            format="json",
        )
        self.assertEqual(permissions.status_code, status.HTTP_200_OK, permissions.data)
        access.refresh_from_db()
        self.assertTrue(access.can_view_academics)
        self.assertFalse(access.can_view_finance)
        self.assertTrue(access.can_view_attendance)

        reset = self.client.post(url, {"action": "reset_password", "access_id": access.pk}, format="json")
        self.assertEqual(reset.status_code, status.HTTP_200_OK, reset.data)
        new_password = reset.data["credential"]["temporary_password"]
        self.assertTrue(new_password)
        self.assertNotEqual(new_password, "123")
        access.user.refresh_from_db()
        self.assertTrue(access.user.check_password(new_password))

        deactivated = self.client.post(url, {"action": "deactivate", "access_id": access.pk}, format="json")
        self.assertEqual(deactivated.status_code, status.HTTP_200_OK, deactivated.data)
        access.refresh_from_db()
        self.assertFalse(access.is_active)

        reactivated = self.client.post(url, {"action": "reactivate", "access_id": access.pk}, format="json")
        self.assertEqual(reactivated.status_code, status.HTTP_200_OK, reactivated.data)
        access.refresh_from_db()
        self.assertTrue(access.is_active)
        self.assertTrue(access.is_verified)


class WorkspaceExportTests(WorkflowCompletionFixture):
    def test_csv_and_print_exports_use_workspace_data(self):
        csv_response = self.client.get(
            reverse("api_workspace_export", kwargs={"resource": "students"}),
            {"format": "csv", "q": "Workflow Student"},
        )
        self.assertEqual(csv_response.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", csv_response["Content-Type"])
        csv_text = csv_response.content.decode("utf-8")
        self.assertIn("Workflow Student", csv_text)
        self.assertIn("Student", csv_text)

        print_response = self.client.get(
            reverse("api_workspace_export", kwargs={"resource": "students"}),
            {"format": "print", "q": "Workflow Student"},
        )
        self.assertEqual(print_response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", print_response["Content-Type"])
        self.assertIn("Workflow Student", print_response.content.decode("utf-8"))

    def test_unknown_export_is_rejected(self):
        response = self.client.get(
            reverse("api_workspace_export", kwargs={"resource": "not-a-report"}),
            {"format": "csv"},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class RoleAccessMatrixTests(APITestCase):
    def test_operational_roles_keep_least_privilege_boundaries(self):
        self.assertEqual(ROLE_RESOURCES["Admin"], {"*"})
        self.assertEqual(ROLE_RESOURCES["Head Teacher"], {"*"})

        self.assertTrue({"results", "attendance", "timetable", "parents"}.issubset(ROLE_RESOURCES["Director of Studies"]))
        self.assertNotIn("finance", ROLE_RESOURCES["Director of Studies"])

        self.assertTrue({"fees", "fees-payments", "finance", "finance-budgets"}.issubset(ROLE_RESOURCES["Bursar"]))
        self.assertNotIn("results", ROLE_RESOURCES["Bursar"])

        for role in ("Teacher", "Class Teacher"):
            self.assertTrue({"students", "classes", "results", "attendance", "timetable"}.issubset(ROLE_RESOURCES[role]))
            self.assertNotIn("finance", ROLE_RESOURCES[role])
            self.assertNotIn("audit", ROLE_RESOURCES[role])

        self.assertIn("admissions", ROLE_RESOURCES["Admissions Officer"])
        self.assertNotIn("finance", ROLE_RESOURCES["Admissions Officer"])
        self.assertEqual(ROLE_RESOURCES["Librarian"], {"students", "library", "communication"})
        self.assertTrue({"students", "results", "attendance", "fees", "communication"}.issubset(ROLE_RESOURCES["Parent"]))
