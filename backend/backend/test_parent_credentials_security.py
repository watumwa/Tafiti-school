from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from app.models import AcademicYear, Class, ParentAccess, Section, Stream, Student, Term
from app.services.parent_portal import activate_parent_access, reset_parent_password


User = get_user_model()


@override_settings(PARENT_TEMP_PASSWORD_HOURS=24)
class ParentCredentialSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "safe-admin-password")
        cls.year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        cls.term = Term.objects.create(
            academic_year=cls.year,
            term="1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 1),
            is_current=True,
        )
        cls.section = Section.objects.create(section_name="Primary")
        cls.school_class = Class.objects.create(name="Primary One", code="P1", section=cls.section)
        cls.stream = Stream.objects.create(stream="Blue")

    def make_student(self, *, name="Child One", contact="0772000000"):
        return Student.objects.create(
            student_name=name,
            gender="M",
            birthdate=date(2018, 1, 1),
            nationality="Ugandan",
            religion="Muslim",
            address="Kampala",
            guardian="Parent One",
            relationship="Parent",
            contact=contact,
            academic_year=self.year,
            current_class=self.school_class,
            stream=self.stream,
            term=self.term,
        )

    def test_activation_generates_random_one_time_password(self):
        access = activate_parent_access(student=self.make_student(), verified_by=self.admin)
        temporary_password = getattr(access, "temporary_password", None)

        self.assertIsNotNone(temporary_password)
        self.assertGreaterEqual(len(temporary_password), 12)
        self.assertNotEqual(temporary_password, "123")
        self.assertTrue(access.user.check_password(temporary_password))
        self.assertFalse(access.user.check_password("123"))
        self.assertTrue(access.must_change_password)
        self.assertGreater(access.temporary_password_expires_at, timezone.now())

        access.refresh_from_db()
        self.assertFalse(hasattr(access, "temporary_password"), "Plaintext credential must never be persisted.")

    def test_linking_sibling_preserves_existing_private_password(self):
        first = activate_parent_access(student=self.make_student(), verified_by=self.admin)
        first.user.set_password("private-parent-password")
        first.user.save(update_fields=("password",))
        ParentAccess.objects.filter(pk=first.pk).update(
            must_change_password=False,
            temporary_password_expires_at=None,
        )

        second = activate_parent_access(
            student=self.make_student(name="Child Two", contact="0772 000 000"),
            verified_by=self.admin,
        )
        second.user.refresh_from_db()

        self.assertEqual(first.user_id, second.user_id)
        self.assertTrue(second.user.check_password("private-parent-password"))
        self.assertFalse(second.must_change_password)
        self.assertIsNone(getattr(second, "temporary_password", None))

    def test_reset_rotates_to_new_random_temporary_password(self):
        access = activate_parent_access(student=self.make_student(), verified_by=self.admin)
        first_temporary_password = access.temporary_password

        user = reset_parent_password(user_id=access.user_id, actor=self.admin)
        reset_password = getattr(user, "temporary_password", None)

        self.assertIsNotNone(reset_password)
        self.assertNotEqual(reset_password, "123")
        self.assertNotEqual(reset_password, first_temporary_password)
        self.assertTrue(user.check_password(reset_password))
        self.assertFalse(user.check_password(first_temporary_password))

        access.refresh_from_db()
        self.assertTrue(access.must_change_password)
        self.assertGreater(access.temporary_password_expires_at, timezone.now())
