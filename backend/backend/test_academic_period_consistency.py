from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from app.models import AcademicYear, Term


class AcademicPeriodConsistencyTests(TestCase):
    def test_new_current_academic_year_closes_previous_current_year(self):
        first = AcademicYear.objects.create(academic_year="2025", is_current=True)
        second = AcademicYear.objects.create(academic_year="2026", is_current=True)

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(AcademicYear.objects.filter(is_current=True).count(), 1)

    def test_new_current_term_closes_all_previous_current_terms(self):
        year_2025 = AcademicYear.objects.create(academic_year="2025", is_current=False)
        year_2026 = AcademicYear.objects.create(academic_year="2026", is_current=True)

        historical = Term.objects.create(
            academic_year=year_2025,
            term="1",
            start_date=date(2025, 2, 3),
            end_date=date(2025, 5, 2),
            is_current=True,
        )
        first = Term.objects.create(
            academic_year=year_2026,
            term="1",
            start_date=date(2026, 2, 2),
            end_date=date(2026, 5, 1),
            is_current=True,
        )
        second = Term.objects.create(
            academic_year=year_2026,
            term="2",
            start_date=date(2026, 5, 25),
            end_date=date(2026, 8, 21),
            is_current=True,
        )

        historical.refresh_from_db()
        first.refresh_from_db()
        second.refresh_from_db()

        self.assertFalse(historical.is_current)
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(Term.objects.filter(is_current=True).count(), 1)

    def test_term_rejects_end_date_before_start_date(self):
        year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        term = Term(
            academic_year=year,
            term="1",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 4, 30),
            is_current=True,
        )

        with self.assertRaises(ValidationError):
            term.save()
