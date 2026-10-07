import csv
import io
from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import (
    AcademicClass,
    AcademicClassStream,
    AcademicYear,
    AuditLog,
    Class,
    ClassRegister,
    Section,
    Staff,
    Stream,
    Student,
    StudentBill,
    Term,
)


class StudentBulkImportTests(APITestCase):
    columns = [
        "Reg No (leave blank for auto)", "Student Name", "Gender",
        "Birth Date (YYYY-MM-DD)", "Nationality", "Religion", "Address",
        "Guardian", "Relationship", "Guardian Contact", "Academic Year",
        "Current Class", "Stream", "Term (1/2/3)",
    ]

    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="bulk-import-admin",
            email="bulk-import@example.test",
            password="test-password",
        )
        self.client.force_authenticate(user=self.admin)
        section = Section.objects.create(section_name="Bulk Import Primary")
        year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        term = Term.objects.create(
            academic_year=year,
            term="1",
            start_date=date(2026, 2, 1),
            end_date=date(2026, 5, 1),
            is_current=True,
        )
        school_class = Class.objects.create(name="Primary Four", code="P4", section=section)
        stream = Stream.objects.create(stream="Blue")
        teacher = Staff.objects.create(
            first_name="Bulk",
            last_name="Teacher",
            birth_date=date(1990, 1, 1),
            gender="F",
            address="Kampala",
            marital_status="U",
            contacts="0700112233",
            email="bulk-teacher@example.test",
            qualification="Diploma",
            hire_date=date(2020, 1, 1),
            department="Academic",
            salary=1,
            staff_status="Active",
        )
        academic_class = AcademicClass.objects.create(
            section=section,
            Class=school_class,
            academic_year=year,
            term=term,
            fees_amount=450000,
        )
        AcademicClassStream.objects.create(
            academic_class=academic_class,
            stream=stream,
            class_teacher=teacher,
        )
        self.url = reverse("api_workspace_student_bulk_import")

    def _upload(self, rows):
        target = io.StringIO()
        writer = csv.writer(target)
        writer.writerow(["STUDENT REGISTRATION DATA"])
        writer.writerow(self.columns)
        writer.writerows(rows)
        upload = SimpleUploadedFile(
            "students.csv",
            target.getvalue().encode("utf-8"),
            content_type="text/csv",
        )
        return self.client.post(self.url, {"file": upload}, format="multipart")

    def _row(self, name, contact, *, gender="F", birthdate="2015-03-04"):
        return [
            "", name, gender, birthdate, "Ugandan", "Protestant", "Kampala",
            f"{name} Guardian", "Parent", contact, "2026", "P4", "Blue", "1",
        ]

    def test_template_describes_atomic_csv_gateway(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["atomic"])
        self.assertEqual(response.data["columns"], self.columns)
        self.assertEqual(response.data["sample"][10:14], ["2026", "P4", "Blue", "1"])

    def test_invalid_row_rolls_back_the_entire_batch(self):
        response = self._upload([
            self._row("Valid Learner", "0700000001"),
            self._row("Invalid Learner", "0700000002", gender="Unknown"),
        ])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(Student.objects.count(), 0)
        self.assertEqual(ClassRegister.objects.count(), 0)
        self.assertEqual(StudentBill.objects.count(), 0)
        self.assertTrue(any("Row 4" in error for error in response.data["errors"]))

    def test_valid_batch_registers_students_classes_bills_and_audit(self):
        response = self._upload([
            self._row("First Learner", "0700000011"),
            self._row("Second Learner", "0700000012", gender="M", birthdate="2015-06-07"),
        ])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["created_count"], 2)
        self.assertEqual(Student.objects.count(), 2)
        self.assertEqual(ClassRegister.objects.count(), 2)
        self.assertEqual(StudentBill.objects.count(), 2)
        audit = AuditLog.objects.get(object_repr="Bulk student registration")
        self.assertEqual(audit.changes["students_created"], 2)
