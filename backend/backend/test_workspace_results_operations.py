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
    Result,
    ResultBatch,
    Section,
    Stream,
    Student,
    Subject,
    Term,
)


class ResultsOperationsWorkspaceTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="results-ops-admin",
            email="results-ops@example.test",
            password="A-strong-test-password-123",
        )
        self.client.force_authenticate(user=self.admin)

        year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        term = Term.objects.create(
            academic_year=year,
            term="1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            is_current=True,
        )
        section = Section.objects.create(section_name="Results Operations")
        class_record = Class.objects.create(name="Primary Five", code="P5-OPS", section=section)
        stream = Stream.objects.create(stream="North")
        academic_class = AcademicClass.objects.create(
            section=section,
            Class=class_record,
            academic_year=year,
            term=term,
            fees_amount=500000,
        )
        class_stream = AcademicClassStream.objects.create(
            academic_class=academic_class,
            stream=stream,
        )
        student = Student.objects.create(
            reg_no="RESULTS-OPS-001",
            student_name="Results Operations Student",
            gender="F",
            birthdate=date(2015, 1, 1),
            nationality="Ugandan",
            religion="Muslim",
            address="Kampala",
            guardian="Results Guardian",
            relationship="Parent",
            contact="0700123456",
            academic_year=year,
            current_class=class_record,
            stream=stream,
            term=term,
            is_active=True,
        )
        ClassRegister.objects.create(
            academic_class_stream=class_stream,
            student=student,
            payment_status="Paid",
        )
        subject = Subject.objects.create(
            code="OPS-MTC",
            name="Operations Mathematics",
            description="Mathematics",
            credit_hours=1,
            section=section,
            type="Core",
        )
        assessment_type = AssessmentType.objects.create(
            name="OPERATIONS TEST",
            weight=Decimal("100.00"),
        )
        assessment = Assessment.objects.create(
            academic_class=academic_class,
            assessment_type=assessment_type,
            subject=subject,
            date=date(2026, 2, 20),
            out_of=100,
            is_done=True,
        )
        batch = ResultBatch.objects.create(
            assessment=assessment,
            status="VERIFIED",
            submitted_by=self.admin,
            submitted_at=date(2026, 2, 21),
            verified_by=self.admin,
            verified_at=date(2026, 2, 22),
        )
        Result.objects.create(
            assessment=assessment,
            student=student,
            score=Decimal("82.00"),
            batch=batch,
            status="VERIFIED",
        )

    def test_results_operations_overview(self):
        response = self.client.get(
            reverse("api_workspace_results_operations", kwargs={"screen": "overview"}),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["metrics"][0]["value"], 1)
        self.assertEqual(response.data["metrics"][3]["value"], 1)
        self.assertEqual(response.data["rows"][0]["status_code"], "VERIFIED")
        self.assertEqual(response.data["rows"][0]["missing"], 0)

    def test_report_card_readiness_uses_verified_batches(self):
        response = self.client.get(
            reverse("api_workspace_results_operations", kwargs={"screen": "report-cards"}),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["rows"]), 1)
        self.assertEqual(response.data["rows"][0]["status"], "Ready")
        self.assertEqual(response.data["rows"][0]["verified_assessments"], 1)

    def test_performance_excludes_unverified_results(self):
        response = self.client.get(
            reverse("api_workspace_results_operations", kwargs={"screen": "performance"}),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["metrics"][0]["value"], 1)
        self.assertEqual(response.data["subjects"][0]["average"], "82.0")
        self.assertEqual(response.data["classes"][0]["average"], "82.0")
