from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from app.models import AcademicYear, Class, Section, Stream, Student, Term
from app.services.parent_portal import activate_parent_access, reset_parent_password


User = get_user_model()


class ParentCredentialSecurityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "admin-safe-password")
        self.year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        self.term = Term.objects.create(
            academic_year=self.year,
            term="1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 1),
            is_current=True,
        )
        self.section = Section.objects.create(section_name="Primary")
        self.school_class = Class.objects.create(name="Primary One", code="P1", section=self.section)
        self.stream = Stream.objects.create(stream="Blue")

    def make_student(self, contact="0772000000"):
        return Student.objects.create(
            student_name="Secure Parent Child",
            gender="M",
            birthdate=date(2018, 1, 1),
            nationality="Ugandan",
            religion="Muslim",
            address="Kampala",
            guardian="Secure Parent",
            relationship="Parent",
            contact=contact,
            academic_year=self.year,
            current_class=self.school_class,
            stream=self.stream,
            term=self.term,
        )

    def test_activation_uses_unique_non_default_one_time_password(self):
        access = activate_parent_access(student=self.make_student(), verified_by=self.admin)
        temporary_password = getattr(access, "_temporary_password", "")
        self.assertTrue(temporary_password)
        self.assertGreaterEqual(len(temporary_password), 12)
        self.assertNotEqual(temporary_password, "123")
        self.assertTrue(access.user.check_password(temporary_password))
        self.assertFalse(access.user.check_password("123"))
        self.assertTrue(access.must_change_password)
        self.assertIsNotNone(access.temporary_password_expires_at)

    def test_reset_rotates_the_temporary_password(self):
        access = activate_parent_access(student=self.make_student("0772111000"), verified_by=self.admin)
        first_password = getattr(access, "_temporary_password", "")
        user = reset_parent_password(user_id=access.user_id, actor=self.admin)
        second_password = getattr(user, "_temporary_password", "")
        self.assertTrue(second_password)
        self.assertNotEqual(first_password, second_password)
        self.assertFalse(user.check_password(first_password))
        self.assertTrue(user.check_password(second_password))


class AcademicCurrentPeriodTests(TestCase):
    def test_saving_current_year_closes_previous_year(self):
        first = AcademicYear.objects.create(academic_year="2025", is_current=True)
        second = AcademicYear.objects.create(academic_year="2026", is_current=True)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(AcademicYear.objects.filter(is_current=True).count(), 1)

    def test_saving_current_term_closes_previous_term_in_same_year(self):
        year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        first = Term.objects.create(
            academic_year=year,
            term="1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 1),
            is_current=True,
        )
        second = Term.objects.create(
            academic_year=year,
            term="2",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 8, 1),
            is_current=True,
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(Term.objects.filter(academic_year=year, is_current=True).count(), 1)
