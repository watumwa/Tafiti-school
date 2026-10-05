from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import AcademicClass, AcademicYear, Class, Payment, Section, Student, StudentBill, Stream, Term
from app.models.finance import BankAccount, BankStatement, BankTransaction


class WorkspaceFinanceTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="finance-admin",
            email="finance-admin@example.test",
            password="A-strong-test-password-123",
        )
        self.client.force_authenticate(user=self.admin)
        year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        term = Term.objects.create(
            academic_year=year,
            term="1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
        )
        section = Section.objects.create(section_name="Finance Test")
        class_record = Class.objects.create(name="Finance Test Class", code="FTC", section=section)
        stream = Stream.objects.create(stream="Finance Test")
        academic_class = AcademicClass.objects.create(
            section=section,
            Class=class_record,
            academic_year=year,
            term=term,
            fees_amount=1000,
        )
        student = Student.objects.create(
            reg_no="FINANCE-TEST-001",
            student_name="Finance Test Student",
            gender="F",
            birthdate=date(2018, 1, 1),
            nationality="Ugandan",
            religion="Muslim",
            address="Test address",
            guardian="Test guardian",
            relationship="Parent",
            contact="0700000000",
            academic_year=year,
            current_class=class_record,
            stream=stream,
            term=term,
        )
        self.bill = StudentBill.objects.get(student=student, academic_class=academic_class)

    def test_finance_resources_and_forms_are_available(self):
        resources = (
            "fees-payments",
            "fees-class-bills",
            "fees-bill-items",
            "finance",
            "finance-budgets",
            "finance-budget-items",
            "finance-expenditure-items",
            "finance-expenses",
            "finance-vendors",
            "finance-income",
        )
        for resource in resources:
            with self.subTest(resource=resource):
                response = self.client.get(
                    reverse("api_workspace_resource", kwargs={"resource": resource}),
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                form_response = self.client.get(
                    reverse("api_workspace_resource_create_form", kwargs={"resource": resource}),
                )
                self.assertEqual(form_response.status_code, status.HTTP_200_OK)

    def test_payment_creation_assigns_bill_recorder_and_reference(self):
        response = self.client.post(
            reverse("api_workspace_resource_create_form", kwargs={"resource": "fees-payments"}),
            {
                "bill": self.bill.pk,
                "payment_date": "2026-10-05",
                "amount": "1.00",
                "payment_method": "Cash",
                "reference_no": "",
                "fee_category": "",
                "notes": "",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        payment = Payment.objects.get(pk=response.data["id"])
        self.assertEqual(payment.bill, self.bill)
        self.assertEqual(payment.recorded_by, self.admin.get_username())
        self.assertTrue(payment.reference_no.startswith(f"PMT-{self.bill.pk}-"))

        invalid_response = self.client.post(
            reverse("api_workspace_resource_create_form", kwargs={"resource": "fees-payments"}),
            {
                "bill": self.bill.pk,
                "payment_date": "2026-10-05",
                "amount": "0",
                "payment_method": "Cash",
            },
            format="json",
        )
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(
            "amount" in invalid_response.data["errors"]
            or "__all__" in invalid_response.data["errors"]
        )

    def test_payment_workspace_summarizes_and_filters_reconciliation(self):
        reconciled_payment = Payment.objects.create(
            bill=self.bill,
            payment_date=date(2026, 10, 6),
            amount="12.00",
            payment_method="Bank",
            fee_category="Tuition",
            reference_no="RECONCILED-001",
            recorded_by=self.admin.get_username(),
        )
        Payment.objects.create(
            bill=self.bill,
            payment_date=date(2026, 10, 5),
            amount="8.00",
            payment_method="Cash",
            fee_category="Tuition",
            reference_no="UNRECONCILED-001",
            recorded_by=self.admin.get_username(),
        )
        account = BankAccount.objects.create(
            bank_name="Test Bank",
            account_number="TEST-ACCOUNT-001",
            account_name="Tafiti School",
            account_type="School",
            balance=1000,
        )
        statement = BankStatement.objects.create(
            bank_account=account,
            statement_date=date(2026, 10, 6),
            opening_balance="0.00",
            closing_balance="12.00",
        )
        BankTransaction.objects.create(
            bank_statement=statement,
            transaction_date=date(2026, 10, 6),
            description="School fees",
            amount="12.00",
            transaction_type="Credit",
            reference=reconciled_payment.reference_no,
            reconciled=True,
            reconciled_with=reconciled_payment,
        )

        all_response = self.client.get(
            reverse("api_workspace_resource", kwargs={"resource": "fees-payments"}),
        )
        self.assertEqual(all_response.status_code, status.HTTP_200_OK)
        self.assertEqual(all_response.data["pagination"]["total"], 2)
        self.assertEqual(all_response.data["metrics"][0]["value"], "UGX 20.00")
        rows_by_reference = {row["reference"]: row for row in all_response.data["rows"]}
        self.assertEqual(rows_by_reference["RECONCILED-001"]["reconciliation"], "Reconciled")
        self.assertEqual(rows_by_reference["UNRECONCILED-001"]["reconciliation"], "Unreconciled")

        unreconciled_response = self.client.get(
            reverse("api_workspace_resource", kwargs={"resource": "fees-payments"}),
            {"status": "unreconciled"},
        )
        self.assertEqual(unreconciled_response.status_code, status.HTTP_200_OK)
        self.assertEqual(unreconciled_response.data["pagination"]["total"], 1)
        self.assertEqual(unreconciled_response.data["rows"][0]["reference"], "UNRECONCILED-001")

    def test_fee_accounts_include_collection_summary_and_status_filters(self):
        Payment.objects.create(
            bill=self.bill,
            payment_date=date(2026, 10, 5),
            amount="300.00",
            payment_method="Cash",
            reference_no="FEE-OVERVIEW-001",
            recorded_by=self.admin.get_username(),
        )
        response = self.client.get(
            reverse("api_workspace_resource", kwargs={"resource": "fees"}),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["metrics"]), 4)
        self.assertEqual(response.data["active_filter"], "all")
        self.assertEqual(response.data["pagination"]["total"], 1)
        self.assertEqual(response.data["rows"][0]["status"], "Partial")
        self.assertEqual(response.data["metrics"][2]["value"], "UGX 700.00")

        paid_response = self.client.get(
            reverse("api_workspace_resource", kwargs={"resource": "fees"}),
            {"status": "paid"},
        )
        self.assertEqual(paid_response.status_code, status.HTTP_200_OK)
        self.assertEqual(paid_response.data["pagination"]["total"], 0)

        partial_response = self.client.get(
            reverse("api_workspace_resource", kwargs={"resource": "fees"}),
            {"status": "partial"},
        )
        self.assertEqual(partial_response.status_code, status.HTTP_200_OK)
        self.assertEqual(partial_response.data["pagination"]["total"], 1)
