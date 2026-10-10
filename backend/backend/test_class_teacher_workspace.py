from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import (
    AcademicClass,
    AcademicClassStream,
    AcademicYear,
    Assessment,
    AssessmentType,
    AttendanceRecord,
    AttendanceSession,
    Class,
    ClassRegister,
    Result,
    Role,
    Section,
    Staff,
    StaffAccount,
    Stream,
    Student,
    Subject,
    Term,
)


class ClassTeacherWorkspaceTests(APITestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        self.term = Term.objects.create(
            academic_year=self.year,
            term="3",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 10),
            is_current=True,
        )
        self.section = Section.objects.create(section_name="Class Teacher Workspace")
        self.class_record = Class.objects.create(name="Primary Four", code="P4-CT", section=self.section)
        self.stream = Stream.objects.create(stream="East")
        self.staff = Staff.objects.create(
            first_name="Class",
            last_name="Teacher",
            birth_date=date(1990, 1, 1),
            gender="F",
            address="Kampala",
            marital_status="U",
            contacts="0700123000",
            email="class-teacher@example.test",
            qualification="Degree",
            nin_no="CTWORK12345678",
            hire_date=date(2020, 1, 1),
            department="Academic",
            salary="1000000.00",
            is_academic_staff=True,
            staff_status="Active",
        )
        role = Role.objects.create(name="Class Teacher")
        self.user = get_user_model().objects.create_user(
            username="class-teacher-workspace",
            password="A-strong-test-password-123",
        )
        StaffAccount.objects.create(staff=self.staff, user=self.user, role=role)
        self.class_stream = AcademicClassStream.objects.create(
            academic_class=AcademicClass.objects.create(
                section=self.section,
                Class=self.class_record,
                academic_year=self.year,
                term=self.term,
                fees_amount=500000,
            ),
            stream=self.stream,
            class_teacher=self.staff,
        )
        self.student = Student.objects.create(
            reg_no="CT-WORK-001",
            student_name="Class Workspace Student",
            gender="F",
            birthdate=date(2016, 1, 1),
            nationality="Ugandan",
            religion="Muslim",
            address="Kampala",
            guardian="Workspace Guardian",
            relationship="Parent",
            contact="0700123999",
            academic_year=self.year,
            current_class=self.class_record,
            stream=self.stream,
            term=self.term,
            is_active=True,
        )
        ClassRegister.objects.create(academic_class_stream=self.class_stream, student=self.student)
        subject = Subject.objects.create(
            code="CTW-MATH",
            name="Workspace Mathematics",
            description="Math",
            credit_hours=1,
            section=self.section,
            type="Core",
        )
        assessment = Assessment.objects.create(
            academic_class=self.class_stream.academic_class,
            assessment_type=AssessmentType.objects.create(name="CLASS WORK", weight=Decimal("100.00")),
            subject=subject,
            date=timezone.localdate(),
            out_of=100,
            is_done=True,
        )
        Result.objects.create(assessment=assessment, student=self.student, score=Decimal("78.00"), status="VERIFIED")
        session = AttendanceSession.objects.create(
            class_stream=self.class_stream,
            subject=subject,
            teacher=self.staff,
            academic_year=self.year,
            term=self.term,
            date=timezone.localdate(),
        )
        AttendanceRecord.objects.create(session=session, student=self.student, status="present")
        self.client.force_authenticate(user=self.user)

    def test_assigned_class_teacher_sees_only_their_class_register_and_follow_up(self):
        response = self.client.get(reverse("api_workspace_my_class"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["assigned_classes"][0]["label"], "P4-CT · East")
        self.assertEqual(response.data["metrics"][0]["value"], 1)
        self.assertEqual(response.data["metrics"][1]["value"], "1/1")
        self.assertEqual(response.data["metrics"][2]["value"], 0)
        self.assertEqual(response.data["students"][0]["admission_no"], "CT-WORK-001")
        self.assertEqual(response.data["students"][0]["attendance_status"], "Present")
        self.assertEqual(response.data["students"][0]["average"], "78.0%")
        self.assertEqual(response.data["students"][0]["remark_status"], "Needed")

    def test_non_class_teacher_cannot_open_my_class_workspace(self):
        role = Role.objects.create(name="Teacher")
        user = get_user_model().objects.create_user(username="regular-teacher", password="A-strong-test-password-123")
        StaffAccount.objects.create(staff=self.staff, user=user, role=role)
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("api_workspace_my_class"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
