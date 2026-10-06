from datetime import date, time

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import (
    AcademicClass,
    AcademicClassStream,
    AcademicYear,
    Class,
    ClassSubjectAllocation,
    Section,
    Staff,
    Stream,
    Subject,
    Term,
    TimeSlot,
    Timetable,
)


class TimetableOperationsTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="timetable-admin", email="timetable@example.test", password="Strong-pass-123"
        )
        self.client.force_authenticate(user=self.admin)
        year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        term = Term.objects.create(academic_year=year, term="1", start_date=date(2026,1,1), end_date=date(2026,4,30), is_current=True)
        section = Section.objects.create(section_name="Timetable Test")
        klass = Class.objects.create(name="P6", code="P6T", section=section)
        stream = Stream.objects.create(stream="East")
        academic_class = AcademicClass.objects.create(section=section, Class=klass, academic_year=year, term=term, fees_amount=0)
        teacher = Staff.objects.create(
            first_name="Time", last_name="Teacher", birth_date=date(1990,1,1), gender="M", address="Kampala",
            marital_status="U", contacts="0700000099", email="time@example.test", qualification="Degree",
            nin_no="CMTIME123456789", hire_date=date(2020,1,1), department="Academic", salary="1000000.00",
            is_academic_staff=True, is_administrator_staff=False, is_support_staff=False, staff_status="Active"
        )
        self.class_stream = AcademicClassStream.objects.create(academic_class=academic_class, stream=stream, class_teacher=teacher)
        subject = Subject.objects.create(code="TMT", name="Timetable Mathematics", description="Math", credit_hours=1, section=section, type="Core")
        self.allocation = ClassSubjectAllocation.objects.create(academic_class_stream=self.class_stream, subject=subject, subject_teacher=teacher)
        self.slot = TimeSlot.objects.create(start_time=time(8,0), end_time=time(8,40))

    def test_hub_lists_stream_allocations_and_periods(self):
        response = self.client.get(reverse("api_workspace_timetable_console", kwargs={"screen":"hub"}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["selected_stream_id"], self.class_stream.pk)
        self.assertEqual(len(response.data["allocations"]), 1)
        self.assertEqual(len(response.data["time_slots"]), 1)

    def test_save_and_delete_entry(self):
        url = reverse("api_workspace_timetable_console", kwargs={"screen":"hub"})
        created = self.client.post(url, {
            "action":"save_entry", "class_stream_id":self.class_stream.pk, "weekday":"MON",
            "time_slot_id":self.slot.pk, "allocation_id":self.allocation.pk
        }, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)
        entry_id = created.data["entry"]["id"]
        self.assertTrue(Timetable.objects.filter(pk=entry_id, teacher=self.allocation.subject_teacher).exists())
        deleted = self.client.post(url, {"action":"delete_entry", "class_stream_id":self.class_stream.pk, "entry_id":entry_id}, format="json")
        self.assertEqual(deleted.status_code, status.HTTP_200_OK)
        self.assertFalse(Timetable.objects.filter(pk=entry_id).exists())

    def test_locked_timetable_rejects_changes(self):
        url = reverse("api_workspace_timetable_console", kwargs={"screen":"hub"})
        locked = self.client.post(url, {"action":"toggle_lock", "class_stream_id":self.class_stream.pk, "locked":True}, format="json")
        self.assertEqual(locked.status_code, status.HTTP_200_OK)
        blocked = self.client.post(url, {
            "action":"save_entry", "class_stream_id":self.class_stream.pk, "weekday":"MON",
            "time_slot_id":self.slot.pk, "allocation_id":self.allocation.pk
        }, format="json")
        self.assertEqual(blocked.status_code, status.HTTP_409_CONFLICT)
