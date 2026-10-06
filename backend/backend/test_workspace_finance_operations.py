from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.crypto import get_random_string
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import (
    AcademicClass,
    AcademicClassStream,
    AcademicYear,
    BankAccount,
    BankStatement,
    BankTransaction,
    BillItem,
    Class,
    ClassRegister,
    Payment,
    Section,
    Staff,
    Stream,
    Student,
    StudentBill,
    StudentBillItem,
    Term,
)


class FinanceOperationsTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="finance-ops-admin",
            email="finance-ops@example.test",
            password=get_random_string(24),
        )
        self.client.force_authenticate(user=self.admin)
        self.year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        self.term1 = Term.objects.create(academic_year=self.year, term="1", start_date=date(2026, 1, 5), end_date=date(2026, 4, 24), is_current=False)
        self.term2 = Term.objects.create(academic_year=self.year, term="2", start_date=date(2026, 5, 18), end_date=date(2026, 8, 21), is_current=True)
        section = Section.objects.create(section_name="Finance Ops")
        school_class = Class.objects.create(name="Primary Four", code="P4", section=section)
        stream = Stream.objects.create(stream="Blue")
        teacher = Staff.objects.create(
            first_name="Finance", last_name="Teacher", birth_date=date(1990, 1, 1), gender="M", address="Kampala",
            marital_status="U", contacts="0700009876", email="finance-teacher@example.test", qualification="Degree",
            nin_no="CMFIN123456789", hire_date=date(2020, 1, 1), department="Academic", salary="1000000.00",
            is_academic_staff=True, is_administrator_staff=False, is_support_staff=False, staff_status="Active",
        )
        self.class1 = AcademicClass.objects.create(section=section, Class=school_class, academic_year=self.year, term=self.term1, fees_amount=Decimal("100000"))
        self.class2 = AcademicClass.objects.create(section=section, Class=school_class, academic_year=self.year, term=self.term2, fees_amount=Decimal("120000"))
        stream1 = AcademicClassStream.objects.create(academic_class=self.class1, stream=stream, class_teacher=teacher)
        AcademicClassStream.objects.create(academic_class=self.class2, stream=stream, class_teacher=teacher)
        self.student = Student.objects.create(
            reg_no="FIN-001", student_name="Finance Student", gender="M", birthdate=date(2016, 1, 1),
            nationality="Ugandan", religion="Muslim", address="Kampala", guardian="Finance Parent",
            relationship="Parent", contact="0700001234", academic_year=self.year, current_class=school_class,
            stream=stream, term=self.term2, is_active=True,
        )
        ClassRegister.objects.create(academic_class_stream=stream1, student=self.student)
        self.fee_item = BillItem.objects.create(item_name="Activity Fee", category="One Off", bill_duration="None", description="Activity fee")

    def url(self, screen):
        return reverse("api_workspace_finance_operations", kwargs={"screen": screen})

    def test_bulk_billing_creates_class_template_and_student_charge(self):
        response = self.client.post(self.url("billing"), {
            "class_ids": [self.class1.pk], "bill_item_id": self.fee_item.pk, "amount": "45000",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        bill = StudentBill.objects.get(student=self.student, academic_class=self.class1)
        charge = StudentBillItem.objects.get(bill=bill, bill_item=self.fee_item)
        self.assertEqual(charge.amount, Decimal("45000.00"))

        response = self.client.post(self.url("billing"), {
            "class_ids": [self.class1.pk], "bill_item_id": self.fee_item.pk, "amount": "50000",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(StudentBillItem.objects.filter(bill=bill, bill_item=self.fee_item).count(), 1)
        self.assertEqual(StudentBillItem.objects.get(bill=bill, bill_item=self.fee_item).amount, Decimal("50000.00"))

    def test_carry_forward_posts_outstanding_balance_once(self):
        source_bill = StudentBill.objects.create(student=self.student, academic_class=self.class1, due_date=self.term1.end_date)
        StudentBillItem.objects.create(bill=source_bill, bill_item=self.fee_item, description="Outstanding fee", amount=Decimal("60000"))

        first = self.client.post(self.url("carry-forward"), {
            "source_term_id": self.term1.pk, "target_term_id": self.term2.pk, "active_students_only": True,
        }, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK, first.data)
        self.assertEqual(first.data["posted_count"], 1)
        target_bill = StudentBill.objects.get(student=self.student, academic_class=self.class2)
        carry_forward = target_bill.items.get(description__icontains="Balance brought forward")
        self.assertEqual(carry_forward.amount, Decimal("60000.00"))

        second = self.client.post(self.url("carry-forward"), {
            "source_term_id": self.term1.pk, "target_term_id": self.term2.pk, "active_students_only": True,
        }, format="json")
        self.assertEqual(second.status_code, status.HTTP_200_OK, second.data)
        self.assertEqual(target_bill.items.filter(description__icontains="Balance brought forward").count(), 1)

    def test_reconciliation_matches_exact_credit_to_payment(self):
        bill, _ = StudentBill.objects.get_or_create(student=self.student, academic_class=self.class2)
        payment = Payment.objects.create(
            bill=bill, payment_date=date(2026, 6, 1), amount=Decimal("50000"), payment_method="Bank",
            reference_no="PAY-FIN-001", recorded_by="admin",
        )
        account = BankAccount.objects.create(bank_name="Test Bank", account_number="00112233", account_name="School", account_type="Current", balance=0)
        statement = BankStatement.objects.create(bank_account=account, statement_date=date(2026, 6, 1), opening_balance=0, closing_balance=50000)
        bank_tx = BankTransaction.objects.create(
            bank_statement=statement, transaction_date=date(2026, 6, 1), description="School fee", amount=Decimal("50000"),
            transaction_type="Credit", reference="BANK-001",
        )

        response = self.client.post(self.url("reconciliation"), {"transaction_id": bank_tx.pk, "payment_id": payment.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        bank_tx.refresh_from_db()
        self.assertTrue(bank_tx.reconciled)
        self.assertEqual(bank_tx.reconciled_with_id, payment.pk)

    def test_reconciliation_rejects_amount_mismatch(self):
        bill, _ = StudentBill.objects.get_or_create(student=self.student, academic_class=self.class2)
        payment = Payment.objects.create(
            bill=bill, payment_date=date(2026, 6, 2), amount=Decimal("40000"), payment_method="Bank",
            reference_no="PAY-FIN-002", recorded_by="admin",
        )
        account = BankAccount.objects.create(bank_name="Test Bank", account_number="00998877", account_name="School Two", account_type="Current", balance=0)
        statement = BankStatement.objects.create(bank_account=account, statement_date=date(2026, 6, 2), opening_balance=0, closing_balance=50000)
        bank_tx = BankTransaction.objects.create(
            bank_statement=statement, transaction_date=date(2026, 6, 2), description="School fee", amount=Decimal("50000"),
            transaction_type="Credit", reference="BANK-002",
        )
        response = self.client.post(self.url("reconciliation"), {"transaction_id": bank_tx.pk, "payment_id": payment.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        bank_tx.refresh_from_db()
        self.assertFalse(bank_tx.reconciled)
