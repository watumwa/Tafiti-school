from datetime import date
from decimal import Decimal

from django.test import TestCase

from app.forms.student import StudentForm
from app.models import (
    AcademicClass,
    AcademicClassStream,
    AcademicYear,
    Class,
    Section,
    Staff,
    Stream,
    Term,
)
from app.selectors.classes import get_current_term


class StudentCurrentStreamBindingTests(TestCase):
    def _staff(self):
        return Staff.objects.create(
            first_name="Class",
            last_name="Teacher",
            birth_date=date(1990, 1, 1),
            gender="M",
            address="Kampala",
            marital_status="U",
            contacts="0700000999",
            email="stream-teacher@example.test",
            qualification="Degree",
            hire_date=date(2020, 1, 1),
            department="Academic",
            salary=Decimal("1000000.00"),
            is_academic_staff=True,
            staff_status="Active",
        )

    def setUp(self):
        self.year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        self.term_two = Term.objects.create(
            academic_year=self.year,
            term="2",
            start_date=date(2026, 5, 18),
            end_date=date(2026, 8, 21),
            is_current=False,
        )
        self.term_three = Term.objects.create(
            academic_year=self.year,
            term="3",
            start_date=date(2026, 9, 7),
            end_date=date(2026, 12, 4),
            is_current=True,
        )
        section = Section.objects.create(section_name="Primary")
        self.class_record = Class.objects.create(name="Primary Four", code="P4", section=section)
        self.stream = Stream.objects.create(stream="-")
        self.teacher = self._staff()
        previous_class = AcademicClass.objects.create(
            section=section,
            Class=self.class_record,
            academic_year=self.year,
            term=self.term_two,
            fees_amount=500000,
        )
        self.current_class = AcademicClass.objects.create(
            section=section,
            Class=self.class_record,
            academic_year=self.year,
            term=self.term_three,
            fees_amount=500000,
        )
        AcademicClassStream.objects.create(
            academic_class=previous_class,
            stream=self.stream,
            class_teacher=self.teacher,
        )

    def _form_data(self, stream_id=None):
        return {
            "lin_number": "",
            "schoolpay_number": "",
            "residency_status": "Day",
            "student_name": "New Learner",
            "gender": "F",
            "birthdate": "2015-02-20",
            "nationality": "Ugandan",
            "religion": "Muslim",
            "address": "Wakiso",
            "guardian": "Guardian Name",
            "relationship": "Mother",
            "contact": "0762630570",
            "current_class": str(self.class_record.pk),
            "stream": str(stream_id or self.stream.pk),
            "is_active": "true",
        }

    def test_current_term_is_scoped_to_current_academic_year(self):
        old_year = AcademicYear.objects.create(academic_year="2025", is_current=False)
        Term.objects.create(
            academic_year=old_year,
            term="3",
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 1),
            is_current=True,
        )
        self.assertEqual(get_current_term(), self.term_three)

    def test_form_repairs_missing_current_stream_from_previous_term(self):
        self.assertFalse(
            AcademicClassStream.objects.filter(
                academic_class=self.current_class,
                stream=self.stream,
            ).exists()
        )

        form = StudentForm(data=self._form_data())
        self.assertTrue(form.is_valid(), form.errors)

        repaired = AcademicClassStream.objects.get(
            academic_class=self.current_class,
            stream=self.stream,
        )
        self.assertEqual(repaired.class_teacher, self.teacher)

    def test_existing_current_stream_configuration_does_not_restore_removed_old_stream(self):
        current_stream = Stream.objects.create(stream="Blue")
        AcademicClassStream.objects.create(
            academic_class=self.current_class,
            stream=current_stream,
            class_teacher=self.teacher,
        )

        form = StudentForm(data=self._form_data(stream_id=self.stream.pk))
        self.assertFalse(form.is_valid())
        self.assertIn("stream", form.errors)
        self.assertFalse(
            AcademicClassStream.objects.filter(
                academic_class=self.current_class,
                stream=self.stream,
            ).exists()
        )
