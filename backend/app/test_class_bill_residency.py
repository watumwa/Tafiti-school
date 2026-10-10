from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from app.models import (
    AcademicClass,
    AcademicYear,
    BillItem,
    Class,
    ClassBill,
    Section,
    Student,
    StudentBill,
    Stream,
    Term,
)
from app.fee_policy_signals import _selected_class_bill
from backend.workspace_forms import WorkspaceClassBillForm


class ClassBillResidencyPolicyTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        self.term = Term.objects.create(
            academic_year=self.year,
            term="1",
            start_date=date(2026, 1, 5),
            end_date=date(2026, 4, 24),
            is_current=True,
        )
        self.section = Section.objects.create(section_name="Primary")
        self.class_record = Class.objects.create(name="Primary Six", code="P6", section=self.section)
        self.stream = Stream.objects.create(stream="A")
        self.academic_class = AcademicClass.objects.create(
            section=self.section,
            Class=self.class_record,
            academic_year=self.year,
            term=self.term,
            fees_amount=Decimal("500000"),
            day_fees_amount=Decimal("450000"),
            boarding_fees_amount=Decimal("850000"),
        )
        self.item = BillItem.objects.create(
            item_name="Lunch",
            category="One Off",
            bill_duration="Termly",
            description="Lunch fee",
        )

    def student(self, *, reg_no, residency):
        return Student.objects.create(
            reg_no=reg_no,
            residency_status=residency,
            student_name=f"{residency} Learner",
            gender="F",
            birthdate=date(2015, 1, 1),
            nationality="Ugandan",
            religion="Muslim",
            address="Kampala",
            guardian="Guardian",
            relationship="Parent",
            contact=f"0700{reg_no[-4:]}",
            academic_year=self.year,
            current_class=self.class_record,
            stream=self.stream,
            term=self.term,
            is_active=True,
        )

    def test_workspace_form_uses_fixed_applies_to_dropdown(self):
        form = WorkspaceClassBillForm()
        self.assertIn("applies_to", form.fields)
        self.assertEqual(
            list(form.fields["applies_to"].choices),
            [
                ("All", "All students"),
                ("Day", "Day students only"),
                ("Boarding", "Boarding students only"),
            ],
        )

    def test_same_fee_item_can_have_day_and_boarding_amounts(self):
        day_policy = ClassBill.objects.create(
            academic_class=self.academic_class,
            bill_item=self.item,
            applies_to=ClassBill.APPLIES_DAY,
            amount=Decimal("120000"),
        )
        boarding_policy = ClassBill.objects.create(
            academic_class=self.academic_class,
            bill_item=self.item,
            applies_to=ClassBill.APPLIES_BOARDING,
            amount=Decimal("200000"),
        )

        self.assertNotEqual(day_policy.pk, boarding_policy.pk)
        self.assertEqual(ClassBill.objects.filter(academic_class=self.academic_class, bill_item=self.item).count(), 2)

    def test_duplicate_same_residency_policy_is_rejected(self):
        ClassBill.objects.create(
            academic_class=self.academic_class,
            bill_item=self.item,
            applies_to=ClassBill.APPLIES_DAY,
            amount=Decimal("120000"),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ClassBill.objects.create(
                    academic_class=self.academic_class,
                    bill_item=self.item,
                    applies_to=ClassBill.APPLIES_DAY,
                    amount=Decimal("125000"),
                )

    def test_exact_residency_policy_wins_over_all_students_fallback(self):
        ClassBill.objects.create(
            academic_class=self.academic_class,
            bill_item=self.item,
            applies_to=ClassBill.APPLIES_ALL,
            amount=Decimal("100000"),
        )
        day_policy = ClassBill.objects.create(
            academic_class=self.academic_class,
            bill_item=self.item,
            applies_to=ClassBill.APPLIES_DAY,
            amount=Decimal("120000"),
        )
        boarding_policy = ClassBill.objects.create(
            academic_class=self.academic_class,
            bill_item=self.item,
            applies_to=ClassBill.APPLIES_BOARDING,
            amount=Decimal("200000"),
        )

        day_student = self.student(reg_no="DAY-0001", residency="Day")
        boarding_student = self.student(reg_no="BRD-0002", residency="Boarding")

        self.assertEqual(_selected_class_bill(self.academic_class, self.item, day_student), day_policy)
        self.assertEqual(_selected_class_bill(self.academic_class, self.item, boarding_student), boarding_policy)

    def test_automatic_student_billing_uses_correct_residency_amount(self):
        ClassBill.objects.create(
            academic_class=self.academic_class,
            bill_item=self.item,
            applies_to=ClassBill.APPLIES_DAY,
            amount=Decimal("120000"),
        )
        ClassBill.objects.create(
            academic_class=self.academic_class,
            bill_item=self.item,
            applies_to=ClassBill.APPLIES_BOARDING,
            amount=Decimal("200000"),
        )
        day_student = self.student(reg_no="DAY-0003", residency="Day")
        boarding_student = self.student(reg_no="BRD-0004", residency="Boarding")

        day_bill = StudentBill.objects.get(student=day_student, academic_class=self.academic_class)
        boarding_bill = StudentBill.objects.get(student=boarding_student, academic_class=self.academic_class)
        day_line = day_bill.items.get(bill_item=self.item)
        boarding_line = boarding_bill.items.get(bill_item=self.item)

        self.assertEqual(day_line.amount, Decimal("120000"))
        self.assertEqual(boarding_line.amount, Decimal("200000"))

    def test_new_policy_is_added_to_existing_matching_student_accounts(self):
        day_student = self.student(reg_no="DAY-0005", residency="Day")
        boarding_student = self.student(reg_no="BRD-0006", residency="Boarding")
        day_bill = StudentBill.objects.get(student=day_student, academic_class=self.academic_class)
        boarding_bill = StudentBill.objects.get(student=boarding_student, academic_class=self.academic_class)
        self.assertFalse(day_bill.items.filter(bill_item=self.item).exists())
        self.assertFalse(boarding_bill.items.filter(bill_item=self.item).exists())

        ClassBill.objects.create(
            academic_class=self.academic_class,
            bill_item=self.item,
            applies_to=ClassBill.APPLIES_BOARDING,
            amount=Decimal("200000"),
        )

        self.assertFalse(day_bill.items.filter(bill_item=self.item, amount__gt=0).exists())
        boarding_line = boarding_bill.items.get(bill_item=self.item)
        self.assertEqual(boarding_line.amount, Decimal("200000"))
