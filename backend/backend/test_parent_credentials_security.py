from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.crypto import get_random_string

from app.models import AcademicYear, Class, ParentAccess, Section, Stream, Student, Term
from app.services.parent_portal import activate_parent_access, reset_parent_password


User = get_user_model()


@override_settings(PARENT_TEMP_PASSWORD_HOURS=24, FRONTEND_URL="http://localhost:3000")
class ParentCredentialSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin", "admin@example.com", get_random_string(24))
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

    @staticmethod
    def setup_parts(setup_url):
        params = parse_qs(urlparse(setup_url).query)
        return params["uid"][0], params["token"][0]

    def test_activation_issues_setup_link_without_exposing_password(self):
        access = activate_parent_access(student=self.make_student(), verified_by=self.admin)

        self.assertIsNone(getattr(access, "temporary_password", None))
        self.assertIn("/parent/setup?", access.setup_url)
        self.assertTrue(access.must_change_password)
        self.assertGreater(access.temporary_password_expires_at, timezone.now())

        reloaded = ParentAccess.objects.get(pk=access.pk)
        self.assertFalse(hasattr(reloaded, "setup_url"))
        self.assertFalse(hasattr(reloaded, "temporary_password"))

    def test_setup_link_creates_private_password_and_is_one_time(self):
        access = activate_parent_access(student=self.make_student(), verified_by=self.admin)
        uid, token = self.setup_parts(access.setup_url)
        new_password = "Parent-Private-2026!Secure"

        response = self.client.post(
            "/api/auth/parent/setup/confirm/",
            data={"uid": uid, "token": token, "password": new_password, "confirm_password": new_password},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        access.user.refresh_from_db()
        access.refresh_from_db()
        self.assertTrue(access.user.check_password(new_password))
        self.assertFalse(access.must_change_password)
        self.assertIsNone(access.temporary_password_expires_at)

        reused = self.client.post(
            "/api/auth/parent/setup/confirm/",
            data={"uid": uid, "token": token, "password": "Another-Private-2026!", "confirm_password": "Another-Private-2026!"},
            content_type="application/json",
        )
        self.assertEqual(reused.status_code, 400)

    def test_expired_setup_link_is_rejected(self):
        access = activate_parent_access(student=self.make_student(), verified_by=self.admin)
        uid, token = self.setup_parts(access.setup_url)
        ParentAccess.objects.filter(user=access.user).update(
            temporary_password_expires_at=timezone.now() - timedelta(minutes=1)
        )
        response = self.client.post(
            "/api/auth/parent/setup/confirm/",
            data={"uid": uid, "token": token, "password": "Parent-Private-2026!Secure", "confirm_password": "Parent-Private-2026!Secure"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_linking_sibling_preserves_existing_private_password(self):
        first = activate_parent_access(student=self.make_student(), verified_by=self.admin)
        private_password = get_random_string(24)
        first.user.set_password(private_password)
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
        self.assertTrue(second.user.check_password(private_password))
        self.assertFalse(second.must_change_password)
        self.assertIsNone(getattr(second, "temporary_password", None))
        self.assertIsNone(getattr(second, "setup_url", None))

    def test_reset_rotates_to_new_one_time_setup_link(self):
        access = activate_parent_access(student=self.make_student(), verified_by=self.admin)
        original_setup_url = access.setup_url

        user = reset_parent_password(user_id=access.user_id, actor=self.admin)

        self.assertIsNone(getattr(user, "temporary_password", None))
        self.assertIn("/parent/setup?", user.setup_url)
        self.assertNotEqual(user.setup_url, original_setup_url)
        access.refresh_from_db()
        self.assertTrue(access.must_change_password)
        self.assertGreater(access.temporary_password_expires_at, timezone.now())
