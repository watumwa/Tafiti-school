from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from app.models import (
    AcademicClass,
    AcademicClassStream,
    AcademicYear,
    Class,
    ClassRegister,
    ClassSubjectAllocation,
    Payment,
    Section,
    Staff,
    Stream,
    Student,
    StudentBill,
    StudentCredit,
    Subject,
    Term,
    TimeSlot,
    Timetable,
)


class AcademicPeriodConsistencyTests(TestCase):
    def test_new_current_academic_year_closes_previous_current_year(self):
        first = AcademicYear.objects.create(academic_year="2025", is_current=True)
        second = AcademicYear.objects.create(academic_year="2026", is_current=True)

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(AcademicYear.objects.filter(is_current=True).count(), 1)

    def test_new_current_term_only_closes_current_term_in_same_year(self):
        year_2025 = AcademicYear.objects.create(academic_year="2025", is_current=False)
        year_2026 = AcademicYear.objects.create(academic_year="2026", is_current=True)

        historical = Term.objects.create(
            academic_year=year_2025,
            term="1",
            start_date=date(2025, 2, 3),
            end_date=date(2025, 5, 2),
            is_current=True,
        )
        first = Term.objects.create(
            academic_year=year_2026,
            term="1",
            start_date=date(2026, 2, 2),
            end_date=date(2026, 5, 1),
            is_current=True,
        )
        second = Term.objects.create(
            academic_year=year_2026,
            term="2",
            start_date=date(2026, 5, 25),
            end_date=date(2026, 8, 21),
            is_current=True,
        )

        historical.refresh_from_db()
        first.refresh_from_db()
        second.refresh_from_db()

        self.assertTrue(historical.is_current)
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(Term.objects.filter(academic_year=year_2026, is_current=True).count(), 1)

    def test_term_rejects_end_date_before_start_date(self):
        year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        term = Term(
            academic_year=year,
            term="1",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 4, 30),
            is_current=True,
        )

        with self.assertRaises(ValidationError):
            term.save()

    def test_new_current_term_rolls_forward_registers_teaching_finance_and_credit_once(self):
        admin = get_user_model().objects.create_superuser(
            username="term-rollover-admin",
            email="rollover@example.test",
            password="test-password",
        )
        year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        term_one = Term.objects.create(
            academic_year=year,
            term="1",
            start_date=date(2026, 1, 5),
            end_date=date(2026, 4, 24),
            is_current=True,
        )
        section = Section.objects.create(section_name="Rollover Primary")
        school_class = Class.objects.create(name="Primary Four", code="P4", section=section)
        stream = Stream.objects.create(stream="North")
        teacher = Staff.objects.create(
            first_name="Rollover", last_name="Teacher", birth_date=date(1990, 1, 1),
            gender="F", address="Kampala", marital_status="U", contacts="0700555000",
            email="rollover-teacher@example.test", qualification="Degree",
            hire_date=date(2020, 1, 1), department="Academic", salary=1,
            staff_status="Active",
        )
        source_class = AcademicClass.objects.create(
            section=section,
            Class=school_class,
            academic_year=year,
            term=term_one,
            fees_amount=Decimal("1000.00"),
        )
        source_stream = AcademicClassStream.objects.create(
            academic_class=source_class,
            stream=stream,
            class_teacher=teacher,
        )
        subject = Subject.objects.create(
            code="ENG-LP", name="English", credit_hours=5, section=section, type="Core",
        )
        allocation = ClassSubjectAllocation.objects.create(
            academic_class_stream=source_stream,
            subject=subject,
            subject_teacher=teacher,
        )
        slot = TimeSlot.objects.create(start_time=time(8, 0), end_time=time(8, 40))
        Timetable.objects.create(
            class_stream=source_stream,
            weekday="MON",
            time_slot=slot,
            subject=subject,
            teacher=teacher,
            allocation=allocation,
        )

        def learner(name, contact):
            student = Student.objects.create(
                student_name=name, gender="F", birthdate=date(2015, 1, 1),
                nationality="Ugandan", religion="Protestant", address="Kampala",
                guardian=f"{name} Guardian", relationship="Parent", contact=contact,
                academic_year=year, current_class=school_class, stream=stream, term=term_one,
            )
            ClassRegister.objects.create(academic_class_stream=source_stream, student=student)
            return student

        balance_student = learner("Balance Learner", "0700000101")
        credit_student = learner("Credit Learner", "0700000102")
        balance_bill = StudentBill.objects.get(student=balance_student, academic_class=source_class)
        credit_bill = StudentBill.objects.get(student=credit_student, academic_class=source_class)
        Payment.objects.create(
            bill=balance_bill, payment_date=date(2026, 2, 1), amount=Decimal("600.00"),
            payment_method="Cash", reference_no="TERM-BALANCE-1", recorded_by=admin.username,
        )
        Payment.objects.create(
            bill=credit_bill, payment_date=date(2026, 2, 1), amount=Decimal("1100.00"),
            payment_method="Cash", reference_no="TERM-CREDIT-1", recorded_by=admin.username,
        )
        self.assertEqual(
            StudentCredit.objects.get(student=credit_student, is_applied=False).amount,
            Decimal("100.00"),
        )

        term_two = Term.objects.create(
            academic_year=year,
            term="2",
            start_date=date(2026, 5, 18),
            end_date=date(2026, 8, 21),
            is_current=True,
        )

        target_class = AcademicClass.objects.get(Class=school_class, academic_year=year, term=term_two)
        target_stream = AcademicClassStream.objects.get(academic_class=target_class, stream=stream)
        self.assertEqual(target_stream.class_teacher, teacher)
        self.assertTrue(ClassSubjectAllocation.objects.filter(
            academic_class_stream=target_stream, subject=subject, subject_teacher=teacher,
        ).exists())
        self.assertTrue(Timetable.objects.filter(
            class_stream=target_stream, weekday="MON", time_slot=slot, subject=subject,
        ).exists())
        self.assertEqual(ClassRegister.objects.filter(academic_class_stream=target_stream).count(), 2)

        carried_bill = StudentBill.objects.get(student=balance_student, academic_class=target_class)
        credited_bill = StudentBill.objects.get(student=credit_student, academic_class=target_class)
        self.assertEqual(carried_bill.balance, Decimal("1400.00"))
        self.assertEqual(credited_bill.balance, Decimal("900.00"))
        self.assertFalse(StudentCredit.objects.filter(student=credit_student, amount__gt=0, is_applied=False).exists())

        term_two.save()
        self.assertEqual(ClassRegister.objects.filter(academic_class_stream=target_stream).count(), 2)
        self.assertEqual(
            carried_bill.items.filter(bill_item__item_name="Balance Brought Forward").count(),
            1,
        )
