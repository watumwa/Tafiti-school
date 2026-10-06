from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import (
    AcademicClass,
    AcademicClassStream,
    AcademicYear,
    AdmissionApplication,
    AdmissionCycle,
    AdmissionStatusHistory,
    Class,
    ClassRegister,
    Section,
    Student,
    StudentBill,
    Stream,
    Term,
)


class WorkspaceAdmissionsTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admissions-admin",
            email="admissions-admin@example.test",
            password="A-strong-test-password-123",
        )
        self.client.force_authenticate(user=self.admin)

        today = timezone.localdate()
        self.year = AcademicYear.objects.create(academic_year=str(today.year), is_current=True)
        self.term = Term.objects.create(
            academic_year=self.year,
            term="1",
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=90),
            is_current=True,
        )
        self.section = Section.objects.create(section_name="Admissions Test")
        self.class_record = Class.objects.create(name="Admissions Class", code="ADM", section=self.section)
        self.stream = Stream.objects.create(stream="Admissions Stream")
        self.academic_class = AcademicClass.objects.create(
            section=self.section,
            Class=self.class_record,
            academic_year=self.year,
            term=self.term,
            fees_amount=500000,
        )
        self.class_stream = AcademicClassStream.objects.create(
            academic_class=self.academic_class,
            stream=self.stream,
        )
        self.cycle = AdmissionCycle.objects.create(
            name="Admissions Test Intake",
            academic_year=self.year,
            opens_on=today - timedelta(days=10),
            closes_on=today + timedelta(days=30),
            is_active=True,
        )
        self.application = AdmissionApplication.objects.create(
            cycle=self.cycle,
            student_name="Admissions Test Learner",
            gender="F",
            birthdate=today.replace(year=today.year - 8),
            nationality="Ugandan",
            religion="Muslim",
            address="Kampala",
            applying_class=self.class_record,
            preferred_stream=self.stream,
            previous_school="Previous School",
            guardian="Admissions Guardian",
            relationship="Parent",
            contact="0700111222",
            status=AdmissionApplication.STATUS_SUBMITTED,
            source=AdmissionApplication.SOURCE_INTERNAL,
            created_by=self.admin,
        )
        AdmissionStatusHistory.objects.create(
            application=self.application,
            to_status=AdmissionApplication.STATUS_SUBMITTED,
            notes="Submitted for review.",
            changed_by=self.admin,
        )

    def test_applications_workspace_returns_pipeline_counts_and_rows(self):
        response = self.client.get(
            reverse("api_workspace_admissions", kwargs={"screen": "applications"}),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Admissions")
        self.assertEqual(response.data["metrics"][0]["value"], 1)
        self.assertEqual(len(response.data["rows"]), 1)
        self.assertEqual(response.data["rows"][0]["application_number"], self.application.application_number)
        self.assertEqual(response.data["rows"][0]["status_code"], AdmissionApplication.STATUS_SUBMITTED)

        filtered = self.client.get(
            reverse("api_workspace_admissions", kwargs={"screen": "applications"}),
            {"status": AdmissionApplication.STATUS_REVIEW},
        )
        self.assertEqual(filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(filtered.data["rows"], [])

    def test_application_detail_exposes_allowed_next_steps_and_timeline(self):
        response = self.client.get(
            reverse(
                "api_workspace_admissions_record",
                kwargs={"screen": "application", "pk": self.application.pk},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["application"]["student_name"] if "student_name" in response.data["application"] else response.data["application"]["applicant"], self.application.student_name)
        self.assertIn(
            AdmissionApplication.STATUS_REVIEW,
            [item["value"] for item in response.data["allowed_transitions"]],
        )
        self.assertEqual(len(response.data["history"]), 1)
        self.assertFalse(response.data["can_enroll"])

    def test_status_transition_is_validated_and_audited(self):
        url = reverse(
            "api_workspace_admissions_record",
            kwargs={"screen": "application", "pk": self.application.pk},
        )
        invalid = self.client.post(
            url,
            {"action": "transition", "status": AdmissionApplication.STATUS_ACCEPTED},
            format="json",
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            url,
            {
                "action": "transition",
                "status": AdmissionApplication.STATUS_REVIEW,
                "notes": "Documents checked and application moved to review.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, AdmissionApplication.STATUS_REVIEW)
        history = self.application.status_history.order_by("-id").first()
        self.assertEqual(history.from_status, AdmissionApplication.STATUS_SUBMITTED)
        self.assertEqual(history.to_status, AdmissionApplication.STATUS_REVIEW)
        self.assertIn("Documents checked", history.notes)

    def test_accepted_application_enrolls_into_existing_student_master_and_billing(self):
        url = reverse(
            "api_workspace_admissions_record",
            kwargs={"screen": "application", "pk": self.application.pk},
        )
        transitions = [
            AdmissionApplication.STATUS_REVIEW,
            AdmissionApplication.STATUS_SHORTLISTED,
            AdmissionApplication.STATUS_ACCEPTED,
        ]
        for target in transitions:
            response = self.client.post(
                url,
                {"action": "transition", "status": target, "notes": f"Move to {target}."},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        detail = self.client.get(url)
        self.assertTrue(detail.data["can_enroll"])

        enrolled = self.client.post(url, {"action": "enroll"}, format="json")
        self.assertEqual(enrolled.status_code, status.HTTP_201_CREATED, enrolled.data)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, AdmissionApplication.STATUS_ENROLLED)
        self.assertIsNotNone(self.application.enrolled_student_id)

        student = Student.objects.get(pk=self.application.enrolled_student_id)
        self.assertEqual(student.student_name, self.application.student_name)
        self.assertEqual(student.current_class, self.class_record)
        self.assertEqual(student.stream, self.stream)
        self.assertTrue(ClassRegister.objects.filter(student=student, academic_class_stream=self.class_stream).exists())
        self.assertTrue(StudentBill.objects.filter(student=student, academic_class=self.academic_class).exists())
