from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


class AuthenticationAPITests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="school-admin",
            email="admin@example.test",
            password="A-strong-test-password-123",
            first_name="Amina",
            last_name="Kato",
        )

    def login(self, **overrides):
        payload = {
            "identifier": self.admin.username,
            "password": "A-strong-test-password-123",
            "login_context": "admin",
        }
        payload.update(overrides)
        return self.client.post(reverse("api_auth_login"), payload, format="json")

    def test_login_returns_tokens_and_backend_role(self):
        response = self.login(login_context="teacher")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["role"]["label"], "Admin")
        self.assertEqual(response.data["user"]["dashboard_path"], "/dashboard/admin")

    def test_email_identifier_is_supported(self):
        response = self.login(identifier="ADMIN@example.test")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["username"], self.admin.username)

    def test_invalid_credentials_have_a_stable_error_code(self):
        response = self.login(password="wrong-password")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["code"], "invalid_credentials")

    def test_inactive_account_is_reported_separately(self):
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "inactive_account")

    def test_current_user_requires_and_accepts_a_bearer_token(self):
        anonymous = self.client.get(reverse("api_auth_me"))
        self.assertEqual(anonymous.status_code, status.HTTP_401_UNAUTHORIZED)

        login_response = self.login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")
        authenticated = self.client.get(reverse("api_auth_me"))

        self.assertEqual(authenticated.status_code, status.HTTP_200_OK)
        self.assertEqual(authenticated.data["user"]["name"], "Amina Kato")

    def test_account_without_an_assigned_school_role_is_denied(self):
        user = User.objects.create_user(username="unassigned", password="test-password-123")

        response = self.login(identifier=user.username, password="test-password-123")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "portal_access_denied")

    def test_password_reset_request_does_not_reveal_account_existence(self):
        existing = self.client.post(
            reverse("api_auth_password_reset"),
            {"email": self.admin.email},
            format="json",
        )
        missing = self.client.post(
            reverse("api_auth_password_reset"),
            {"email": "missing@example.test"},
            format="json",
        )

        self.assertEqual(existing.status_code, status.HTTP_200_OK)
        self.assertEqual(missing.status_code, status.HTTP_200_OK)
        self.assertEqual(existing.data, missing.data)

    def test_valid_reset_token_changes_the_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.admin.pk))
        token = default_token_generator.make_token(self.admin)

        response = self.client.post(
            reverse("api_auth_password_reset_confirm"),
            {
                "uid": uid,
                "token": token,
                "password": "A-new-strong-password-456",
                "confirm_password": "A-new-strong-password-456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(authenticate(username=self.admin.username, password="A-new-strong-password-456"))
