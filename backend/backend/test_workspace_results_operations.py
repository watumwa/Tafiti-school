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
    Role,
    Section,
    Staff,
    StaffAccount,
    Stream,
    Student,
    Subject,
    Term,
)


class ResultsOperationsWorkspaceTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username="results-ops-admin",
            email="results-ops@example.test",
            password="A-strong-test-password-123",
        )
        self.client.force_authenticate(user=self.admin)

        self.year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        self.term = Term.objects.create(
            academic_year=self.year,
            term="1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            is_current=True,
        )
        self.section = Section.objects.create(section_name="Results Operations")
        self.class_record = Class.objects.create(name="Primary Five", code="P5-OPS", section=self.section)
        self.stream = Stream.objects.create(stream="North")
        self.academic_class = AcademicClass.objects.create(
            section=self.section,
            Class=self.class_record,
            academic_year=self.year,
            term=self.term,
            fees_amount=500000,
        )
        self.teacher = Staff.objects.create(
            first_name="Results",
            last_name="Teacher",
            birth_date=date(1990, 1, 1),
            gender="M",
            address="Kampala",
            marital_status="U",
            contacts="0700999000",
            email="results-teacher@example.test",
            qualification="Degree",
            nin_no="CMOPS123456789",
            hire_date=date(2020, 1, 1),
            department="Academic",
            salary="1000000.00",
            is_academic_staff=True,
            is_administrator_staff=False,
            is_support_staff=False,
            staff_status="Active",
        )
        self.class_stream = AcademicClassStream.objects.create(
            academic_class=self.academic_class,
            stream=self.stream,
            class_teacher=self.teacher,
        )
        self.student = Student.objects.create(
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
            academic_year=self.year,
            current_class=self.class_record,
            stream=self.stream,
            term=self.term,
            is_active=True,
        )
        ClassRegister.objects.create(
            academic_class_stream=self.class_stream,
            student=self.student,
            payment_status="Paid",
        )
        self.subject = Subject.objects.create(
            code="OPS-MTC",
            name="Operations Mathematics",
            description="Mathematics",
            credit_hours=1,
            section=self.section,
            type="Core",
        )
        assessment_type = AssessmentType.objects.create(
            name="OPERATIONS TEST",
            weight=Decimal("100.00"),
        )
        self.assessment = Assessment.objects.create(
            academic_class=self.academic_class,
            assessment_type=assessment_type,
            subject=self.subject,
            date=date(2026, 2, 20),
            out_of=100,
            is_done=True,
        )
        self.batch = ResultBatch.objects.create(
            assessment=self.assessment,
            status="VERIFIED",
            submitted_by=self.admin,
            submitted_at=date(2026, 2, 21),
            verified_by=self.admin,
            verified_at=date(2026, 2, 22),
        )
        Result.objects.create(
            assessment=self.assessment,
            student=self.student,
            score=Decimal("82.00"),
            batch=self.batch,
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
        self.assertEqual(response.data["rows"][0]["status"], "Ready for remarks")
        self.assertEqual(response.data["rows"][0]["verified_assessments"], 1)

    def test_performance_excludes_unverified_results(self):
        response = self.client.get(
            reverse("api_workspace_results_operations", kwargs={"screen": "performance"}),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["metrics"][0]["value"], 1)
        self.assertEqual(response.data["subjects"][0]["average"], "82.0")
        self.assertEqual(response.data["classes"][0]["average"], "82.0")

    def _authenticate_staff_role(self, username, role_name, *, class_teacher=False):
        User = get_user_model()
        staff = self.teacher if class_teacher else Staff.objects.create(
            first_name=username.title(),
            last_name="User",
            birth_date=date(1991, 1, 1),
            gender="M",
            address="Kampala",
            marital_status="U",
            contacts=f"0700{User.objects.count():06d}"[-10:],
            email=f"{username}@example.test",
            qualification="Degree",
            hire_date=date(2021, 1, 1),
            department="Academic",
            salary="1000000.00",
            is_academic_staff=True,
            is_administrator_staff=False,
            is_support_staff=False,
            staff_status="Active",
        )
        user = User.objects.create_user(username=username, password="A-strong-test-password-123")
        role, _ = Role.objects.get_or_create(name=role_name)
        staff.roles.add(role)
        StaffAccount.objects.create(staff=staff, user=user, role=role)
        self.client.force_authenticate(user=user)
        return user, staff

    def test_class_teacher_can_save_and_submit_report_remarks_after_verification(self):
        teacher_user, _ = self._authenticate_staff_role("class-teacher", "Class Teacher", class_teacher=True)
        endpoint = reverse(
            "api_workspace_results_operations_record",
            kwargs={"screen": "report-class", "pk": self.academic_class.pk},
        )

        opened = self.client.get(endpoint)
        self.assertEqual(opened.status_code, status.HTTP_200_OK)
        self.assertTrue(opened.data["ready"])
        self.assertTrue(opened.data["permissions"]["prepare"])
        self.assertFalse(opened.data["permissions"]["approve"])

        saved = self.client.post(endpoint, {
            "action": "save_remarks",
            "remarks": {str(self.student.pk): "Good progress in class."},
        }, format="json")
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        remark = ReportCycleRemark.objects.get(student=self.student, academic_class=self.academic_class)
        self.assertEqual(remark.class_teacher_remark, "Good progress in class.")
        self.assertIsNone(remark.class_teacher_submitted_at)

        submitted = self.client.post(endpoint, {
            "action": "submit_remarks",
            "remarks": {str(self.student.pk): "Good progress in class."},
        }, format="json")
        self.assertEqual(submitted.status_code, status.HTTP_200_OK)
        remark.refresh_from_db()
        self.assertEqual(remark.class_teacher_submitted_by, teacher_user)
        self.assertIsNotNone(remark.class_teacher_submitted_at)

    def test_report_remarks_cannot_submit_until_all_batches_are_verified(self):
        self.batch.status = "PENDING"
        self.batch.save(update_fields=["status"])
        self._authenticate_staff_role("pending-class-teacher", "Class Teacher", class_teacher=True)
        endpoint = reverse(
            "api_workspace_results_operations_record",
            kwargs={"screen": "report-class", "pk": self.academic_class.pk},
        )
        response = self.client.post(endpoint, {
            "action": "submit_remarks",
            "remarks": {str(self.student.pk): "Ready when marks are verified."},
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("verified", response.data["detail"].lower())

    def test_head_teacher_can_approve_submitted_report_remarks(self):
        self._authenticate_staff_role("class-teacher-submit", "Class Teacher", class_teacher=True)
        endpoint = reverse(
            "api_workspace_results_operations_record",
            kwargs={"screen": "report-class", "pk": self.academic_class.pk},
        )
        self.client.post(endpoint, {
            "action": "submit_remarks",
            "remarks": {str(self.student.pk): "Consistent effort throughout the term."},
        }, format="json")

        head_user, _ = self._authenticate_staff_role("head-teacher", "Head Teacher")
        approved = self.client.post(endpoint, {
            "action": "approve_remarks",
            "head_remarks": {str(self.student.pk): "Keep up the good work."},
        }, format="json")
        self.assertEqual(approved.status_code, status.HTTP_200_OK)
        remark = ReportCycleRemark.objects.get(student=self.student, academic_class=self.academic_class)
        self.assertEqual(remark.head_teacher_approved_by, head_user)
        self.assertIsNotNone(remark.head_teacher_approved_at)
        self.assertEqual(remark.head_teacher_remark, "Keep up the good work.")

    def test_unassigned_teacher_cannot_prepare_class_report_remarks(self):
        self._authenticate_staff_role("subject-teacher", "Teacher")
        endpoint = reverse(
            "api_workspace_results_operations_record",
            kwargs={"screen": "report-class", "pk": self.academic_class.pk},
        )
        response = self.client.post(endpoint, {
            "action": "save_remarks",
            "remarks": {str(self.student.pk): "Should not be accepted."},
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
