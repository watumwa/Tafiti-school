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
    AttendanceRecord,
    AttendanceSession,
    AttendanceStatus,
    Class,
    ClassRegister,
    ClassSubjectAllocation,
    Section,
    Staff,
    Stream,
    Student,
    Subject,
    Term,
    TimeSlot,
    Timetable,
)
from app.models.timetables import WeekDay
from app.services.attendance import lock_session


class WorkspaceAttendanceHubTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="attendance-admin",
            email="attendance-admin@example.test",
            password="A-strong-test-password-123",
        )
        self.client.force_authenticate(user=self.admin)

        self.year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        self.term = Term.objects.create(
            academic_year=self.year,
            term="1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_current=True,
        )
        self.section = Section.objects.create(section_name="Attendance Hub")
        self.school_class = Class.objects.create(name="Primary Four", code="P4-HUB", section=self.section)
        self.stream = Stream.objects.create(stream="Blue Hub")
        self.teacher = Staff.objects.create(
            first_name="Hub",
            last_name="Teacher",
            birth_date=date(1990, 1, 1),
            gender="M",
            address="School",
            marital_status="S",
            contacts="0700123456",
            email="hub-teacher@example.test",
            qualification="Diploma",
            hire_date=date(2020, 1, 1),
            department="Academic",
            salary=1,
            staff_status="Active",
            staff_photo=SimpleUploadedFile("hub-teacher.jpg", b"img", content_type="image/jpeg"),
        )
        self.academic_class = AcademicClass.objects.create(
            section=self.section,
            Class=self.school_class,
            academic_year=self.year,
            term=self.term,
            fees_amount=0,
        )
        self.class_stream = AcademicClassStream.objects.create(
            academic_class=self.academic_class,
            stream=self.stream,
            class_teacher=self.teacher,
        )
        self.subject = Subject.objects.create(
            code="ENG-HUB",
            name="English Hub",
            description="English",
            credit_hours=4,
            section=self.section,
            type="Core",
        )
        ClassSubjectAllocation.objects.create(
            academic_class_stream=self.class_stream,
            subject=self.subject,
            subject_teacher=self.teacher,
        )
        self.slot = TimeSlot.objects.create(start_time="08:00", end_time="09:00")
        self.lesson = Timetable.objects.create(
            class_stream=self.class_stream,
            weekday=WeekDay.MONDAY,
            time_slot=self.slot,
            subject=self.subject,
            teacher=self.teacher,
        )
        self.student = Student.objects.create(
            reg_no="ATT-HUB-001",
            student_name="Attendance Hub Learner",
            gender="F",
            birthdate=date(2016, 1, 1),
            nationality="Ugandan",
            religion="Muslim",
            address="Kampala",
            guardian="Hub Guardian",
            relationship="Parent",
            contact="0700111000",
            academic_year=self.year,
            current_class=self.school_class,
            stream=self.stream,
            term=self.term,
            is_active=True,
        )
        ClassRegister.objects.create(academic_class_stream=self.class_stream, student=self.student)
        self.monday = date(2026, 10, 5)

    def hub_url(self):
        return reverse("api_workspace_attendance_console", kwargs={"screen": "hub"})

    def test_today_hub_uses_timetable_and_shows_not_started_lesson(self):
        response = self.client.get(self.hub_url(), {"date": self.monday.isoformat()})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["view"], "today")
        self.assertEqual(len(response.data["scheduled"]), 1)
        row = response.data["scheduled"][0]
        self.assertEqual(row["lesson_id"], self.lesson.pk)
        self.assertIsNone(row["session_id"])
        self.assertEqual(row["status"], "Not started")
        self.assertEqual(row["students"], 1)
        self.assertTrue(row["can_take"])

    def test_start_attendance_creates_session_and_initializes_register(self):
        response = self.client.post(
            self.hub_url(),
            {"action": "start", "lesson_id": self.lesson.pk, "date": self.monday.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        session = AttendanceSession.objects.get(pk=response.data["session_id"])
        self.assertEqual(session.lesson, self.lesson)
        self.assertEqual(session.teacher, self.teacher)
        self.assertEqual(session.date, self.monday)
        record = AttendanceRecord.objects.get(session=session, student=self.student)
        self.assertEqual(record.status, AttendanceStatus.UNMARKED)

        second = self.client.post(
            self.hub_url(),
            {"action": "start", "lesson_id": self.lesson.pk, "date": self.monday.isoformat()},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data["session_id"], session.pk)
        self.assertEqual(AttendanceSession.objects.count(), 1)

    def test_submitted_session_appears_in_history_and_student_report(self):
        started = self.client.post(
            self.hub_url(),
            {"action": "start", "lesson_id": self.lesson.pk, "date": self.monday.isoformat()},
            format="json",
        )
        session = AttendanceSession.objects.get(pk=started.data["session_id"])
        record = AttendanceRecord.objects.get(session=session, student=self.student)
        record.status = AttendanceStatus.ABSENT
        record.captured_by = self.teacher
        record.save()
        lock_session(session, actor_user=self.admin)

        history = self.client.get(
            self.hub_url(),
            {
                "view": "history",
                "date_from": self.monday.isoformat(),
                "date_to": self.monday.isoformat(),
                "state": "submitted",
            },
        )
        self.assertEqual(history.status_code, status.HTTP_200_OK, history.data)
        self.assertEqual(len(history.data["history"]), 1)
        self.assertEqual(history.data["history"][0]["status"], "Submitted")
        self.assertEqual(history.data["history"][0]["absent"], 1)

        report = self.client.get(
            self.hub_url(),
            {
                "view": "reports",
                "date_from": self.monday.isoformat(),
                "date_to": self.monday.isoformat(),
                "class_stream": self.class_stream.pk,
            },
        )
        self.assertEqual(report.status_code, status.HTTP_200_OK, report.data)
        self.assertEqual(len(report.data["reports"]), 1)
        learner = report.data["reports"][0]
        self.assertEqual(learner["student"], self.student.student_name)
        self.assertEqual(learner["absent"], 1)
        self.assertEqual(learner["attendance_rate"], 0.0)
        self.assertEqual(learner["status"], "Below minimum")

    def test_wrong_weekday_cannot_start_scheduled_lesson(self):
        response = self.client.post(
            self.hub_url(),
            {"action": "start", "lesson_id": self.lesson.pk, "date": "2026-10-06"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not scheduled", response.data["detail"].lower())
