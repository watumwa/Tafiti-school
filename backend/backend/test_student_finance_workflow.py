from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import (
    AcademicClass,
    AcademicYear,
    Class,
    Section,
    Student,
    StudentBill,
    StudentCredit,
    StudentFeeAdjustment,
    Stream,
    Term,
)


class StudentFinanceWorkflowTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="finance-workflow-admin",
            email="finance-workflow@example.test",
            password="Strong-password-123",
        )
        self.client.force_authenticate(user=self.user)
        self.year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        self.term = Term.objects.create(
            academic_year=self.year,
            term="1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            is_current=True,
        )
        self.section = Section.objects.create(section_name="Finance Workflow")
        self.class_record = Class.objects.create(name="Primary Five", code="P5-FIN", section=self.section)
        self.stream = Stream.objects.create(stream="Blue")
        self.academic_class = AcademicClass.objects.create(
            section=self.section,
            Class=self.class_record,
            academic_year=self.year,
            term=self.term,
            fees_amount=Decimal("1000.00"),
        )
        self.student = Student.objects.create(
            reg_no="FIN-WORK-001",
            student_name="Finance Workflow Student",
            gender="F",
            birthdate=date(2015, 3, 3),
            nationality="Ugandan",
            religion="Muslim",
            address="Kampala",
            guardian="Parent One",
            relationship="Parent",
            contact="0700001000",
            academic_year=self.year,
            current_class=self.class_record,
            stream=self.stream,
            term=self.term,
        )
        self.bill = StudentBill.objects.get(student=self.student, academic_class=self.academic_class)

    def account_url(self, bill=None):
        return reverse(
            "api_workspace_student_finance_record",
            kwargs={"screen": "account", "pk": (bill or self.bill).pk},
        )

    def test_accounts_directory_exposes_student_bill_and_status(self):
        response = self.client.get(reverse("api_workspace_student_finance", kwargs={"screen": "accounts"}))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data["rows"]), 1)
        row = response.data["rows"][0]
        self.assertEqual(row["student"], self.student.student_name)
        self.assertEqual(row["gross_billed"], "1000.00")
        self.assertEqual(row["status"], "Outstanding")
        self.assertEqual(response.data["metrics"]["outstanding"], "1000.00")

    def test_partial_payment_is_attached_to_student_bill(self):
        response = self.client.post(
            self.account_url(),
            {
                "action": "record_payment",
                "amount": "400.00",
                "payment_date": "2026-02-01",
                "payment_method": "Cash",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.bill.refresh_from_db()
        self.assertEqual(self.bill.amount_paid, Decimal("400.00"))
        self.assertEqual(self.bill.balance, Decimal("600.00"))
        self.assertEqual(self.bill.payment_status_display, "Partial")
        self.assertEqual(response.data["account"]["bill"]["student"], self.student.student_name)

    def test_bursary_reduces_amount_due_without_counting_as_cash(self):
        response = self.client.post(
            self.account_url(),
            {
                "action": "add_adjustment",
                "adjustment_type": "Bursary",
                "calculation_type": "Percentage",
                "value": "50",
                "reason": "Management approved half bursary",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.bill.refresh_from_db()
        self.assertEqual(self.bill.approved_adjustments, Decimal("500.00"))
        self.assertEqual(self.bill.net_amount_due, Decimal("500.00"))
        self.assertEqual(self.bill.amount_paid, Decimal("0"))
        self.assertEqual(self.bill.balance, Decimal("500.00"))
        adjustment = StudentFeeAdjustment.objects.get(bill=self.bill)
        self.assertEqual(adjustment.created_by, self.user.username)
        self.assertEqual(adjustment.status, "Approved")

    def test_overpayment_becomes_student_credit_against_net_bill(self):
        self.client.post(
            self.account_url(),
            {
                "action": "add_adjustment",
                "adjustment_type": "Scholarship",
                "calculation_type": "Fixed",
                "value": "200.00",
                "reason": "Merit scholarship",
            },
            format="json",
        )
        payment_response = self.client.post(
            self.account_url(),
            {
                "action": "record_payment",
                "amount": "900.00",
                "payment_date": "2026-02-02",
                "payment_method": "Cash",
            },
            format="json",
        )
        self.assertEqual(payment_response.status_code, status.HTTP_201_CREATED, payment_response.data)
        self.bill.refresh_from_db()
        self.assertEqual(self.bill.net_amount_due, Decimal("800.00"))
        self.assertEqual(self.bill.balance, Decimal("-100.00"))
        credit = StudentCredit.objects.get(original_bill=self.bill, is_applied=False, description__icontains="overpayment credit")
        self.assertEqual(credit.amount, Decimal("100.00"))

    def test_partial_credit_application_keeps_only_unused_remainder(self):
        StudentCredit.objects.create(
            student=self.student,
            amount=Decimal("300.00"),
            description="Opening family credit",
            original_bill=self.bill,
            is_applied=False,
        )
        applied = self.bill.apply_credit(Decimal("120.00"))
        self.assertEqual(applied, Decimal("120.00"))
        remaining = StudentCredit.objects.get(student=self.student, description="Opening family credit", is_applied=False)
        self.assertEqual(remaining.amount, Decimal("180.00"))
        application = StudentCredit.objects.get(student=self.student, amount=Decimal("-120.00"), is_applied=True)
        self.assertEqual(application.applied_to_bill, self.bill)

    def test_adjustment_cannot_exceed_remaining_gross_bill(self):
        first = self.client.post(
            self.account_url(),
            {"action": "add_adjustment", "adjustment_type": "Bursary", "calculation_type": "Fixed", "value": "800", "reason": "Large bursary"},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(
            self.account_url(),
            {"action": "add_adjustment", "adjustment_type": "Waiver", "calculation_type": "Fixed", "value": "300", "reason": "Would exceed bill"},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
