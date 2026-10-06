from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import AcademicYear, Term


class AcademicPeriodWorkspaceTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="academic-period-admin",
            email="academic-period@example.test",
            password="A-strong-test-password-123",
        )
        self.client.force_authenticate(user=self.admin)
        self.year_2025 = AcademicYear.objects.create(academic_year="2025", is_current=True)
        self.term_2025 = Term.objects.create(
            academic_year=self.year_2025,
            term="1",
            start_date=date(2025, 1, 6),
            end_date=date(2025, 4, 25),
            is_current=True,
        )

    def tool_url(self, tool):
        return reverse("api_workspace_academic_tool", kwargs={"tool": tool})

    def record_url(self, tool, pk):
        return reverse("api_workspace_academic_tool_record", kwargs={"tool": tool, "pk": pk})

    def test_setting_current_year_clears_previous_year_and_incompatible_term(self):
        response = self.client.post(
            self.tool_url("academic-years"),
            {"academic_year": "2026", "is_current": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        self.year_2025.refresh_from_db()
        self.term_2025.refresh_from_db()
        year_2026 = AcademicYear.objects.get(academic_year="2026")
        self.assertTrue(year_2026.is_current)
        self.assertFalse(self.year_2025.is_current)
        self.assertFalse(self.term_2025.is_current)

    def test_setting_current_term_also_sets_its_year_current(self):
        year_2026 = AcademicYear.objects.create(academic_year="2026", is_current=False)
        response = self.client.post(
            self.tool_url("terms"),
            {
                "academic_year": year_2026.pk,
                "term": "1",
                "start_date": "2026-01-05",
                "end_date": "2026-04-24",
                "is_current": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        year_2026.refresh_from_db()
        self.year_2025.refresh_from_db()
        self.term_2025.refresh_from_db()
        current_term = Term.objects.get(academic_year=year_2026, term="1")
        self.assertTrue(current_term.is_current)
        self.assertTrue(year_2026.is_current)
        self.assertFalse(self.year_2025.is_current)
        self.assertFalse(self.term_2025.is_current)

    def test_current_term_cannot_be_cleared_without_replacement(self):
        response = self.client.post(
            self.record_url("terms", self.term_2025.pk),
            {
                "academic_year": self.year_2025.pk,
                "term": "1",
                "start_date": "2025-01-06",
                "end_date": "2025-04-25",
                "is_current": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("is_current", response.data["errors"])
        self.term_2025.refresh_from_db()
        self.assertTrue(self.term_2025.is_current)

    def test_term_end_date_cannot_precede_start_date(self):
        response = self.client.post(
            self.tool_url("terms"),
            {
                "academic_year": self.year_2025.pk,
                "term": "2",
                "start_date": "2025-08-01",
                "end_date": "2025-05-01",
                "is_current": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", response.data["errors"])
