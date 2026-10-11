from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from app.models import (
    AcademicClass,
    AcademicClassStream,
    AcademicYear,
    Class,
    Section,
    Staff,
    Stream,
    Student,
    StudentBill,
    Term,
)
from app.services.student_bulk_import import bulk_student_registration
from app.services.students import BulkStudentRegistrationError


class StudentBulkImportIdentityTests(TestCase):
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
        self.class_record = Class.objects.create(name="Primary Four", code="P4", section=self.section)
        self.stream = Stream.objects.create(stream="Blue")
        self.teacher = Staff.objects.create(
            first_name="Bulk",
            last_name="Teacher",
            birth_date=date(1990, 1, 1),
            gender="F",
            address="Kampala",
            marital_status="U",
            contacts="0700000999",
            email="bulk-teacher@example.test",
            qualification="Degree",
            hire_date=date(2020, 1, 1),
            department="Academic",
            salary=Decimal("1000000.00"),
            is_academic_staff=True,
            staff_status="Active",
        )
        self.academic_class = AcademicClass.objects.create(
            section=self.section,
            Class=self.class_record,
            academic_year=self.year,
            term=self.term,
            fees_amount=Decimal("500000"),
            day_fees_amount=Decimal("450000"),
            boarding_fees_amount=Decimal("850000"),
        )
        AcademicClassStream.objects.create(
            academic_class=self.academic_class,
            stream=self.stream,
            class_teacher=self.teacher,
        )

    def upload(self, text):
        return SimpleUploadedFile(
            "students.csv",
            text.encode("utf-8"),
            content_type="text/csv",
        )

    def test_bulk_import_saves_lin_schoolpay_and_student_type(self):
        csv_text = "\n".join([
            "STUDENT REGISTRATION DATA",
            "Reg No (leave blank for auto),LIN (optional),SchoolPay Number (optional),Student Type (Day/Boarding),Student Name,Gender,Birth Date (YYYY-MM-DD),Nationality,Religion,Address,Guardian,Relationship,Guardian Contact,Academic Year,Current Class,Stream,Term (1/2/3)",
            ",U13F0921A44760,SP-000123,Boarding,Jane Example,F,2015-02-20,Ugandan,Protestant,Kampala,Mary Example,Mother,0700000000,2026,P4,Blue,1",
        ])

        result = bulk_student_registration(self.upload(csv_text))

        self.assertEqual(result["created_count"], 1)
        student = Student.objects.get(student_name="Jane Example")
        self.assertEqual(student.lin_number, "U13F0921A44760")
        self.assertEqual(student.schoolpay_number, "SP-000123")
        self.assertEqual(student.residency_status, "Boarding")

        bill = StudentBill.objects.get(student=student, academic_class=self.academic_class)
        school_fees = bill.items.get(bill_item__item_name="School Fees")
        self.assertEqual(school_fees.amount, Decimal("850000"))

    def test_student_type_column_is_required(self):
        csv_text = "\n".join([
            "STUDENT REGISTRATION DATA",
            "Reg No (leave blank for auto),LIN (optional),SchoolPay Number (optional),Student Name,Gender,Birth Date (YYYY-MM-DD),Nationality,Religion,Address,Guardian,Relationship,Guardian Contact,Academic Year,Current Class,Stream,Term (1/2/3)",
            ",U13F0921A44760,SP-000123,Jane Example,F,2015-02-20,Ugandan,Protestant,Kampala,Mary Example,Mother,0700000000,2026,P4,Blue,1",
        ])

        with self.assertRaises(BulkStudentRegistrationError) as caught:
            bulk_student_registration(self.upload(csv_text))

        self.assertIn("residency_status", " ".join(caught.exception.errors))
        self.assertFalse(Student.objects.filter(student_name="Jane Example").exists())

    def test_duplicate_lin_blocks_entire_batch(self):
        csv_text = "\n".join([
            "STUDENT REGISTRATION DATA",
            "Reg No (leave blank for auto),LIN (optional),SchoolPay Number (optional),Student Type (Day/Boarding),Student Name,Gender,Birth Date (YYYY-MM-DD),Nationality,Religion,Address,Guardian,Relationship,Guardian Contact,Academic Year,Current Class,Stream,Term (1/2/3)",
            ",U13F0921A44760,SP-000123,Day,Jane Example,F,2015-02-20,Ugandan,Protestant,Kampala,Mary Example,Mother,0700000000,2026,P4,Blue,1",
            ",U13F0921A44760,SP-000124,Boarding,Amina Example,F,2015-03-10,Ugandan,Muslim,Kampala,Asha Example,Mother,0700000001,2026,P4,Blue,1",
        ])

        with self.assertRaises(BulkStudentRegistrationError) as caught:
            bulk_student_registration(self.upload(csv_text))

        self.assertIn("duplicate LIN", " ".join(caught.exception.errors))
        self.assertFalse(Student.objects.filter(student_name__in=["Jane Example", "Amina Example"]).exists())
