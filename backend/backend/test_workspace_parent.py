from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import (
    AcademicClass,
    AcademicYear,
    Announcement,
    Assessment,
    AssessmentType,
    Class,
    Event,
    ParentAccess,
    ParentNotification,
    Payment,
    Result,
    Section,
    Student,
    StudentBill,
    Subject,
    Stream,
    Term,
)


class WorkspaceParentTests(APITestCase):
    def setUp(self):
        year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        term = Term.objects.create(
            academic_year=year,
            term="1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
            is_current=True,
        )
        section = Section.objects.create(section_name="Parent Workspace")
        class_record = Class.objects.create(
            name="Parent Workspace Class",
            code="PWC",
            section=section,
        )
        stream = Stream.objects.create(stream="Parent Workspace")
        self.academic_class = AcademicClass.objects.create(
            section=section,
            Class=class_record,
            academic_year=year,
            term=term,
            fees_amount=1000,
        )
        student = Student.objects.create(
            reg_no="PARENT-WORKSPACE-001",
            student_name="Parent Workspace Student",
            gender="F",
            birthdate=date(2018, 1, 1),
            nationality="Ugandan",
            religion="Muslim",
            address="Test address",
            guardian="Parent Workspace Guardian",
            relationship="Parent",
            contact="0700000000",
            academic_year=year,
            current_class=class_record,
            stream=stream,
            term=term,
        )
        self.parent = get_user_model().objects.create_user(
            username="parent-workspace",
            password="not-a-real-password",
            first_name="Parent",
        )
        self.access = ParentAccess.objects.create(
            user=self.parent,
            student=student,
            is_verified=True,
            is_active=True,
        )
        subject = Subject.objects.create(
            code="PWS",
            name="Parent Workspace Subject",
            credit_hours=1,
            section=section,
            type="Core",
        )
        assessment_type = AssessmentType.objects.create(
            name="Parent Workspace Assessment",
            weight=100,
        )
        assessment = Assessment.objects.create(
            academic_class=self.academic_class,
            assessment_type=assessment_type,
            subject=subject,
            date=date(2026, 3, 1),
            out_of=100,
        )
        Result.objects.create(
            student=student,
            assessment=assessment,
            score=80,
            status="VERIFIED",
        )
        Result.objects.create(
            student=student,
            assessment=Assessment.objects.create(
                academic_class=self.academic_class,
                assessment_type=AssessmentType.objects.create(
                    name="Unpublished Parent Assessment",
                    weight=100,
                ),
                subject=Subject.objects.create(
                    code="PWU",
                    name="Unpublished Parent Subject",
                    credit_hours=1,
                    section=section,
                    type="Core",
                ),
                date=date(2026, 3, 2),
                out_of=100,
            ),
            score=99,
            status="PENDING",
        )
        Announcement.objects.create(
            title="Parent workspace announcement",
            body="Important parent-only update.",
            audience="parents",
            starts_at=timezone.now() - timedelta(hours=1),
        )
        self.client.force_authenticate(user=self.parent)

    def test_parent_results_only_include_published_verified_marks(self):
        response = self.client.get(
            reverse("api_workspace_resource", kwargs={"resource": "results"}),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["total"], 1)
        self.assertEqual(response.data["rows"][0]["status"], "Verified")
        self.assertEqual(response.data["rows"][0]["score"], "80.00")

    def test_parent_dashboard_includes_scoped_child_results_and_notices(self):
        response = self.client.get(reverse("api_workspace_dashboard"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        portal = response.data["parent_portal"]
        self.assertEqual(len(portal["children"]), 1)
        self.assertEqual(portal["children"][0]["academic_average"], 80.0)
        self.assertEqual(len(portal["recent_results"]), 1)
        self.assertEqual(portal["recent_results"][0]["score"], "80.00")
        self.assertEqual(len(portal["announcements"]), 1)
        self.assertEqual(portal["announcements"][0]["title"], "Parent workspace announcement")
        self.assertEqual(
            {notice["kind"] for notice in response.data["notifications"]},
            {"result", "announcement"},
        )

    def test_parent_navigation_contains_only_parent_portal_modules(self):
        response = self.client.get(reverse("api_workspace_bootstrap"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [
            item["slug"]
            for group in response.data["navigation"]
            for item in group["items"]
        ]
        self.assertEqual(
            slugs,
            [
                "overview",
                "parent-children",
                "parent-attendance",
                "parent-finance",
                "parent-communication",
                "parent-calendar",
                "parent-results",
                "parent-reports",
            ],
        )

    def test_parent_activity_screens_only_offer_children_with_matching_permission(self):
        attendance = self.client.get(reverse("api_workspace_parent", kwargs={"action": "attendance"}))
        finance = self.client.get(reverse("api_workspace_parent", kwargs={"action": "finance"}))

        self.assertEqual(attendance.status_code, status.HTTP_200_OK)
        self.assertEqual(attendance.data["students"], [{"id": self.access.student_id, "name": self.access.student.student_name}])
        self.assertEqual(finance.status_code, status.HTTP_200_OK)
        self.assertEqual(len(finance.data["students"]), 1)

        bill, _ = StudentBill.objects.get_or_create(
            student=self.access.student,
            academic_class=self.academic_class,
        )
        Payment.objects.create(
            bill=bill,
            payment_date=date(2026, 3, 5),
            amount=250,
            payment_method="Cash",
            reference_no="PARENT-REC-001",
            recorded_by="Bursar",
        )
        finance = self.client.get(reverse("api_workspace_parent", kwargs={"action": "finance"}))
        self.assertEqual(finance.data["payments"][0]["reference"], "PARENT-REC-001")

        Event.objects.create(
            title="Parent school event",
            description="Family meeting",
            audience="parents",
            location="School hall",
            start_datetime=timezone.now() + timedelta(days=1),
        )
        calendar = self.client.get(reverse("api_workspace_parent", kwargs={"action": "calendar"}))
        self.assertEqual(calendar.status_code, status.HTTP_200_OK)
        self.assertEqual([event["title"] for event in calendar.data["events"]], ["Parent school event"])

        self.access.can_view_attendance = False
        self.access.can_view_finance = False
        self.access.save(update_fields=("can_view_attendance", "can_view_finance"))

        attendance = self.client.get(reverse("api_workspace_parent", kwargs={"action": "attendance"}))
        finance = self.client.get(reverse("api_workspace_parent", kwargs={"action": "finance"}))

        self.assertEqual(attendance.status_code, status.HTTP_200_OK)
        self.assertEqual(attendance.data["students"], [])
        self.assertEqual(attendance.data["records"], [])
        self.assertEqual(finance.status_code, status.HTTP_200_OK)
        self.assertEqual(finance.data["students"], [])
        self.assertEqual(finance.data["bills"], [])
        self.assertEqual(finance.data["payments"], [])

    def test_parent_can_update_own_contact_profile(self):
        response = self.client.patch(
            reverse("api_workspace_parent", kwargs={"action": "profile"}),
            {"first_name": "Updated", "last_name": "Guardian", "email": "guardian@example.test"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.first_name, "Updated")
        self.assertEqual(self.parent.email, "guardian@example.test")

    def test_parent_can_download_verified_report_only_for_linked_child(self):
        report_url = reverse("api_workspace_parent", kwargs={"action": "report"})
        response = self.client.post(
            report_url,
            {"student_id": self.access.student_id},
            format="json",
        )
        forbidden = self.client.post(
            report_url,
            {"student_id": self.access.student_id + 100000},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content_type"], "application/pdf")
        self.assertTrue(response.data["content_base64"])
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_parent_can_mark_only_own_linked_notifications_read(self):
        notice = ParentNotification.objects.create(
            user=self.parent,
            student=self.access.student,
            kind="attendance",
            title="Attendance update",
            message="A new attendance record is available.",
            source_key="parent-workspace-attendance-test",
        )
        response = self.client.post(
            reverse("api_workspace_parent", kwargs={"action": "notifications-read"}),
            {"notification_id": notice.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notice.refresh_from_db()
        self.assertIsNotNone(notice.read_at)

    def test_admin_dashboard_has_role_metrics_and_seven_day_trends(self):
        admin = get_user_model().objects.create_superuser(
            username="workspace-admin",
            email="workspace-admin@example.test",
            password="test-password",
        )
        self.client.force_authenticate(user=admin)

        response = self.client.get(reverse("api_workspace_dashboard"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["stats"]), 6)
        self.assertEqual(len(response.data["analytics"]["attendance_trend"]), 7)
        self.assertEqual(len(response.data["analytics"]["collection_trend"]), 6)
