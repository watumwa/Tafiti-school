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
    Assessment,
    AssessmentType,
    Class,
    ClassRegister,
    ReportCycleRemark,
    Result,
    ResultBatch,
    Section,
    Staff,
    Stream,
    Student,
    Subject,
    Term,
)


class ReportCardWorkflowTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="report-workflow-admin",
            email="report-workflow@example.test",
            password="A-strong-test-password-123",
        )
        self.client.force_authenticate(user=self.admin)
        self.year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        self.term = Term.objects.create(
            academic_year=self.year,
            term="1",
            start_date=date(2026, 1, 5),
            end_date=date(2026, 4, 24),
            is_current=True,
        )
        section = Section.objects.create(section_name="Report Workflow")
        school_class = Class.objects.create(name="Primary Five", code="P5", section=section)
        stream = Stream.objects.create(stream="Blue")
        self.teacher = Staff.objects.create(
            first_name="Class",
            last_name="Teacher",
            birth_date=date(1990, 1, 1),
            gender="M",
            address="Kampala",
            marital_status="S",
            contacts="0700111222",
            email="class.teacher@example.test",
            qualification="Degree",
            hire_date=date(2020, 1, 1),
            department="Academic",
            salary=Decimal("1000000.00"),
            staff_status="Active",
        )
        self.academic_class = AcademicClass.objects.create(
            section=section,
            Class=school_class,
            academic_year=self.year,
            term=self.term,
            fees_amount=0,
        )
        class_stream = AcademicClassStream.objects.create(
            academic_class=self.academic_class,
            stream=stream,
            class_teacher=self.teacher,
        )
        self.student = Student.objects.create(
            reg_no="REPORT-001",
            student_name="Report Student",
            gender="F",
            birthdate=date(2015, 1, 1),
            nationality="Ugandan",
            religion="Muslim",
            address="Kampala",
            guardian="Report Guardian",
            relationship="Parent",
            contact="0700333444",
            academic_year=self.year,
            current_class=school_class,
            stream=stream,
            term=self.term,
            is_active=True,
        )
        ClassRegister.objects.create(academic_class_stream=class_stream, student=self.student)
        subject = Subject.objects.create(
            code="MTC",
            name="Mathematics",
            credit_hours=1,
            section=section,
            type="Core",
        )
        assessment_type = AssessmentType.objects.create(name="End of Term", weight=Decimal("100.00"))
        assessment = Assessment.objects.create(
            academic_class=self.academic_class,
            assessment_type=assessment_type,
            subject=subject,
            date=date(2026, 4, 10),
            out_of=100,
            is_done=True,
        )
        batch = ResultBatch.objects.create(
            assessment=assessment,
            status="VERIFIED",
            submitted_by=self.admin,
            verified_by=self.admin,
        )
        Result.objects.create(
            assessment=assessment,
            student=self.student,
            score=Decimal("82.00"),
            batch=batch,
            status="VERIFIED",
        )

    def operations_url(self, screen):
        return reverse("api_workspace_results_operations", kwargs={"screen": screen})

    def report_status(self):
        response = self.client.get(self.operations_url("report-cards"))
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data["rows"][0]["status"]

    def test_report_card_progresses_from_remarks_to_approval_to_ready(self):
        self.assertEqual(self.report_status(), "Remarks pending")

        workflow = self.client.get(
            self.operations_url("report-workflow"),
            {"class_id": self.academic_class.pk},
        )
        self.assertEqual(workflow.status_code, status.HTTP_200_OK, workflow.data)
        self.assertTrue(workflow.data["permissions"]["edit"])
        self.assertTrue(workflow.data["permissions"]["approve"])
        self.assertEqual(workflow.data["rows"][0]["status"], "Not started")

        submitted = self.client.post(
            self.operations_url("report-workflow"),
            {
                "action": "submit",
                "class_id": self.academic_class.pk,
                "student_id": self.student.pk,
                "class_teacher_remark": "A strong term with steady progress.",
            },
            format="json",
        )
        self.assertEqual(submitted.status_code, status.HTTP_200_OK, submitted.data)
        self.assertEqual(self.report_status(), "Approval pending")

        approved = self.client.post(
            self.operations_url("report-workflow"),
            {
                "action": "approve",
                "class_id": self.academic_class.pk,
                "student_id": self.student.pk,
                "head_teacher_remark": "Keep up the good work.",
            },
            format="json",
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK, approved.data)
        self.assertEqual(self.report_status(), "Ready")

        remark = ReportCycleRemark.objects.get(student=self.student, academic_class=self.academic_class)
        self.assertIsNotNone(remark.class_teacher_submitted_at)
        self.assertIsNotNone(remark.head_teacher_approved_at)

        reopened = self.client.post(
            self.operations_url("report-workflow"),
            {
                "action": "reopen",
                "class_id": self.academic_class.pk,
                "student_id": self.student.pk,
            },
            format="json",
        )
        self.assertEqual(reopened.status_code, status.HTTP_200_OK, reopened.data)
        self.assertEqual(self.report_status(), "Approval pending")

    def test_empty_class_teacher_remark_cannot_be_submitted(self):
        response = self.client.post(
            self.operations_url("report-workflow"),
            {
                "action": "submit",
                "class_id": self.academic_class.pk,
                "student_id": self.student.pk,
                "class_teacher_remark": "   ",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(ReportCycleRemark.objects.filter(student=self.student).exclude(class_teacher_submitted_at=None).exists())
