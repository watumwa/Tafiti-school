from datetime import date

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from app.forms.student import StudentForm
from app.models.classes import Class, Stream, Term
from app.models.school_settings import AcademicYear, Section
from app.models.students import Student
from app.validators import lin_gender_marker, normalize_uganda_lin, validate_uganda_lin


class UgandaLinValidatorTests(SimpleTestCase):
    def test_accepts_known_structural_examples(self):
        for lin in ("U13F0921A44760", "U15M0521A57754", "U08M0521A47086"):
            with self.subTest(lin=lin):
                validate_uganda_lin(lin)

    def test_rejects_malformed_lins(self):
        invalid = (
            "13F0921A44760",
            "U13X0921A44760",
            "U13F0921B44760",
            "U13F092144760",
            "U13F0921A4476",
            "U13F0921A447600",
        )
        for lin in invalid:
            with self.subTest(lin=lin):
                with self.assertRaises(ValidationError):
                    validate_uganda_lin(lin)

    def test_normalizer_uppercases_and_trims(self):
        self.assertEqual(normalize_uganda_lin("  u13f0921a44760  "), "U13F0921A44760")

    def test_gender_marker_is_available_only_for_valid_lin(self):
        self.assertEqual(lin_gender_marker("U13F0921A44760"), "F")
        self.assertEqual(lin_gender_marker("U15M0521A57754"), "M")
        self.assertEqual(lin_gender_marker("not-a-lin"), "")


class UgandaLinStudentFormTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        self.term = Term.objects.create(
            academic_year=self.year,
            term="1",
            start_date=date(2026, 1, 5),
            end_date=date(2026, 4, 24),
            is_current=True,
        )
        self.section = Section.objects.create(section_name="Primary")
        self.class_record = Class.objects.create(name="Primary Five", code="P5", section=self.section)
        self.stream = Stream.objects.create(stream="Blue")

    def _form_data(self, *, lin="U13F0921A44760", gender="F", name="Amina Learner", contact="0700000001"):
        return {
            "lin_number": lin,
            "schoolpay_number": "SP-TEST-001",
            "residency_status": "Day",
            "student_name": name,
            "gender": gender,
            "birthdate": "2015-05-04",
            "nationality": "Ugandan",
            "religion": "Catholic",
            "address": "Kampala",
            "guardian": "Mary Learner",
            "relationship": "Mother",
            "contact": contact,
            "current_class": self.class_record.pk,
            "stream": self.stream.pk,
            "is_active": True,
        }

    def test_form_normalizes_valid_lin_to_uppercase(self):
        form = StudentForm(data=self._form_data(lin="u13f0921a44760"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["lin_number"], "U13F0921A44760")

    def test_form_rejects_invalid_lin_format(self):
        form = StudentForm(data=self._form_data(lin="U13F0921B44760"))
        self.assertFalse(form.is_valid())
        self.assertIn("lin_number", form.errors)
        self.assertIn("14-character Uganda LIN", form.errors["lin_number"][0])

    def test_gender_marker_mismatch_does_not_block_save(self):
        form = StudentForm(data=self._form_data(lin="U15M0521A57754", gender="F"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_lin_already_assigned_to_another_student(self):
        Student.objects.create(
            reg_no="ST0999",
            lin_number="U13F0921A44760",
            student_name="Existing Learner",
            gender="F",
            birthdate=date(2014, 2, 2),
            nationality="Ugandan",
            religion="Catholic",
            address="Kampala",
            guardian="Existing Guardian",
            relationship="Mother",
            contact="0700000099",
            academic_year=self.year,
            current_class=self.class_record,
            stream=self.stream,
            term=self.term,
            is_active=True,
        )

        form = StudentForm(
            data=self._form_data(
                lin="u13f0921a44760",
                name="Different Learner",
                contact="0700000002",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["lin_number"][0], "This LIN is already assigned to another student.")
