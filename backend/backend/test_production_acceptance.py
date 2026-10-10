from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import (
    AcademicClass,
    AcademicClassStream,
    AcademicYear,
    Assessment,
    AssessmentType,
    Class,
    ClassRegister,
    GradingSystem,
    OutboundMessage,
    Result,
    Role,
    Section,
    Staff,
    StaffAccount,
    Stream,
    Student,
    StudentBill,
    StudentCredit,
    Subject,
    Term,
    TermResult,
)
from app.services.outbound_communications import send_report_ready_notice


User = get_user_model()


def create_staff(*, first_name="Test", last_name="Teacher", contact="0700000001", email="teacher@example.test"):
    return Staff.objects.create(
        first_name=first_name,
        last_name=last_name,
        birth_date=date(1990, 1, 1),
        gender="M",
        address="Kampala",
        marital_status="U",
        contacts=contact,
        email=email,
        qualification="Degree",
        hire_date=date(2020, 1, 1),
        department="Academic",
        salary=Decimal("1000000.00"),
        is_academic_staff=True,
        staff_status="Active",
    )


def academic_fixture(prefix="ACC", fee=1000, day_fee=None, boarding_fee=None):
    year = AcademicYear.objects.create(academic_year="2026", is_current=True)
    term = Term.objects.create(
        academic_year=year,
        term="1",
        start_date=date(2026, 1, 5),
        end_date=date(2026, 4, 24),
        is_current=True,
    )
    section = Section.objects.create(section_name=f"{prefix} Primary")
    class_record = Class.objects.create(name="Primary Five", code=prefix[:3], section=section)
    stream = Stream.objects.create(stream=f"{prefix} Stream")
    teacher = create_staff(
        first_name=prefix,
        last_name="Teacher",
        contact=f"0700{len(prefix):06d}"[-10:],
        email=f"{prefix.lower()}-teacher@example.test",
    )
    academic_class = AcademicClass.objects.create(
        section=section,
        Class=class_record,
        academic_year=year,
        term=term,
        fees_amount=fee,
        day_fees_amount=day_fee,
        boarding_fees_amount=boarding_fee,
    )
    class_stream = AcademicClassStream.objects.create(
        academic_class=academic_class,
        stream=stream,
        class_teacher=teacher,
    )
    return year, term, section, class_record, stream, teacher, academic_class, class_stream


def create_student(*, name, reg_no, year, term, class_record, stream, contact, residency="Day"):
    return Student.objects.create(
        reg_no=reg_no,
        lin_number=f"LIN-{reg_no}",
        schoolpay_number=f"SP-{reg_no}",
        residency_status=residency,
        student_name=name,
        gender="F",
        birthdate=date(2015, 1, 1),
        nationality="Ugandan",
        religion="Muslim",
        address="Kampala",
        guardian=f"{name} Guardian",
        relationship="Parent",
        contact=contact,
        academic_year=year,
        current_class=class_record,
        stream=stream,
        term=term,
        is_active=True,
    )


class AccountRoleWorkspaceAcceptanceTests(APITestCase):
    def test_account_creation_login_and_workspace_switching(self):
        teacher_role = Role.objects.create(name="Teacher", is_system=True)
        class_teacher_role = Role.objects.create(name="Class Teacher", is_system=True)
        staff = create_staff(first_name="Multi", last_name="Role", contact="0700111222", email="multi@example.test")
        staff.roles.add(teacher_role, class_teacher_role)

        admin = User.objects.create_superuser("acceptance-admin", "admin@example.test", "Admin-password-123")
        browser = Client()
        browser.force_login(admin)
        created = browser.post(
            reverse("create_account"),
            {"staff": staff.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(created.status_code, 200)
        payload = created.json()
        self.assertTrue(payload["username"])
        self.assertTrue(payload["temporary_password"])

        account = StaffAccount.objects.select_related("user").get(staff=staff)
        self.assertTrue(account.must_change_password)
        self.assertTrue(account.user.check_password(payload["temporary_password"]))

        first_login = self.client.post(
            reverse("api_auth_login"),
            {"identifier": payload["username"], "password": payload["temporary_password"], "login_context": "teacher"},
            format="json",
        )
        self.assertEqual(first_login.status_code, status.HTTP_200_OK, first_login.data)
        self.assertTrue(first_login.data["user"]["must_change_password"])
        self.assertEqual(len(first_login.data["user"]["roles"]), 2)

        account.must_change_password = False
        account.temporary_password_expires_at = None
        account.save(update_fields=["must_change_password", "temporary_password_expires_at"])

        login = self.client.post(
            reverse("api_auth_login"),
            {"identifier": payload["username"], "password": payload["temporary_password"], "login_context": "teacher"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK, login.data)
        self.assertEqual(login.data["user"]["role"]["label"], "Teacher")
        self.assertEqual(login.data["user"]["dashboard_path"], "/dashboard/teacher")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        switched = self.client.post(
            reverse("api_auth_switch_role"),
            {"role": "class_teacher"},
            format="json",
        )
        self.assertEqual(switched.status_code, status.HTTP_200_OK, switched.data)
        self.assertEqual(switched.data["user"]["role"]["label"], "Class Teacher")
        self.assertEqual(switched.data["user"]["dashboard_path"], "/dashboard/teacher")


class UgandaIdentityAndTermRolloverAcceptanceTests(APITestCase):
    def test_lin_schoolpay_day_boarding_fees_and_term_rollover(self):
        year, term_one, section, class_record, stream, teacher, source_class, source_stream = academic_fixture(
            "UGA", fee=1000, day_fee=800, boarding_fee=1500
        )
        day_student = create_student(
            name="Day Learner", reg_no="UGA-DAY-1", year=year, term=term_one,
            class_record=class_record, stream=stream, contact="0700000201", residency="Day",
        )
        boarding_student = create_student(
            name="Boarding Learner", reg_no="UGA-BRD-1", year=year, term=term_one,
            class_record=class_record, stream=stream, contact="0700000202", residency="Boarding",
        )
        ClassRegister.objects.create(academic_class_stream=source_stream, student=day_student)
        ClassRegister.objects.create(academic_class_stream=source_stream, student=boarding_student)

        day_bill = StudentBill.objects.get(student=day_student, academic_class=source_class)
        boarding_bill = StudentBill.objects.get(student=boarding_student, academic_class=source_class)
        self.assertEqual(day_bill.total_amount, Decimal("800"))
        self.assertEqual(boarding_bill.total_amount, Decimal("1500"))
        self.assertEqual(day_student.lin_number, "LIN-UGA-DAY-1")
        self.assertEqual(day_student.schoolpay_number, "SP-UGA-DAY-1")

        term_two = Term.objects.create(
            academic_year=year,
            term="2",
            start_date=date(2026, 5, 18),
            end_date=date(2026, 8, 21),
            is_current=True,
        )
        target_class = AcademicClass.objects.get(academic_year=year, term=term_two, Class=class_record)
        target_class.refresh_from_db()
        self.assertEqual(target_class.day_fees_amount, 800)
        self.assertEqual(target_class.boarding_fees_amount, 1500)

        rolled_day_bill = StudentBill.objects.get(student=day_student, academic_class=target_class)
        rolled_boarding_bill = StudentBill.objects.get(student=boarding_student, academic_class=target_class)
        self.assertEqual(rolled_day_bill.total_amount, Decimal("800"))
        self.assertEqual(rolled_boarding_bill.total_amount, Decimal("1500"))
        self.assertEqual(
            ClassRegister.objects.filter(academic_class_stream__academic_class=target_class).count(),
            2,
        )


class AssessmentReportPolicyAcceptanceTests(APITestCase):
    def test_report_only_subject_is_visible_but_not_graded_or_computed(self):
        admin = User.objects.create_superuser("report-admin", "report@example.test", "Strong-password-123")
        self.client.force_authenticate(user=admin)
        year, term, section, class_record, stream, teacher, academic_class, class_stream = academic_fixture("RPT", fee=500)
        student = create_student(
            name="Report Learner", reg_no="RPT-001", year=year, term=term,
            class_record=class_record, stream=stream, contact="0700000301",
        )
        ClassRegister.objects.create(academic_class_stream=class_stream, student=student)
        computed_subject = Subject.objects.create(
            code="MATH-RPT", name="Mathematics", credit_hours=5, section=section, type="Core",
            show_on_report=True, include_in_totals=True, calculate_grade=True, include_in_ranking=True,
        )
        report_only_subject = Subject.objects.create(
            code="READ-RPT", name="Reading", credit_hours=1, section=section, type="Core",
            show_on_report=True, include_in_totals=False, calculate_grade=False, include_in_ranking=False,
        )
        assessment_type = AssessmentType.objects.create(name="EOT-RPT", weight=Decimal("100"))
        GradingSystem.objects.create(min_score=80, max_score=100, grade="A", points=1)
        math_assessment = Assessment.objects.create(
            academic_class=academic_class, assessment_type=assessment_type, subject=computed_subject,
            date=date(2026, 3, 1), out_of=100, is_done=True,
        )
        reading_assessment = Assessment.objects.create(
            academic_class=academic_class, assessment_type=assessment_type, subject=report_only_subject,
            date=date(2026, 3, 1), out_of=100, is_done=True,
        )
        math = Result.objects.create(assessment=math_assessment, student=student, score=Decimal("80"), status="VERIFIED")
        reading = Result.objects.create(assessment=reading_assessment, student=student, score=Decimal("95"), status="VERIFIED")

        self.assertEqual(math.grade, "A")
        self.assertEqual(reading.grade, "—")
        self.assertEqual(reading.points, Decimal("0.00"))
        self.assertEqual(reading.actual_score, Decimal("0.00"))

        term_result = TermResult.objects.create(student=student, academic_class=academic_class)
        term_result.calculate_term_result()
        term_result.refresh_from_db()
        self.assertEqual(term_result.total_score, Decimal("80"))
        self.assertEqual(term_result.average_score, Decimal("80"))

        performance = self.client.get(
            reverse("api_workspace_reports", kwargs={"category": "academics"}),
            {"report": "student-performance"},
        )
        self.assertEqual(performance.status_code, status.HTTP_200_OK, performance.data)
        self.assertEqual(performance.data["rows"][0]["average"], "80.00")


class FinanceLifecycleAcceptanceTests(APITestCase):
    def test_bursary_overpayment_credit_rollover_and_financial_statement_balance(self):
        admin = User.objects.create_superuser("finance-acceptance", "finance@example.test", "Strong-password-123")
        self.client.force_authenticate(user=admin)
        year, term_one, section, class_record, stream, teacher, source_class, source_stream = academic_fixture("FIN", fee=1000)
        student = create_student(
            name="Finance Learner", reg_no="FIN-001", year=year, term=term_one,
            class_record=class_record, stream=stream, contact="0700000401",
        )
        ClassRegister.objects.create(academic_class_stream=source_stream, student=student)
        bill = StudentBill.objects.get(student=student, academic_class=source_class)
        account_url = reverse("api_workspace_student_finance_record", kwargs={"screen": "account", "pk": bill.pk})

        bursary = self.client.post(
            account_url,
            {"action": "add_adjustment", "adjustment_type": "Bursary", "calculation_type": "Percentage", "value": "50", "reason": "Half bursary"},
            format="json",
        )
        self.assertEqual(bursary.status_code, status.HTTP_201_CREATED, bursary.data)
        payment = self.client.post(
            account_url,
            {"action": "record_payment", "amount": "600", "payment_date": "2026-02-01", "payment_method": "Cash"},
            format="json",
        )
        self.assertEqual(payment.status_code, status.HTTP_201_CREATED, payment.data)
        bill.refresh_from_db()
        self.assertEqual(bill.net_amount_due, Decimal("500"))
        self.assertEqual(bill.balance, Decimal("-100"))
        self.assertEqual(StudentCredit.objects.get(student=student, is_applied=False).amount, Decimal("100"))

        statement = self.client.get(
            reverse("api_workspace_finance_reports"),
            {"report": "financial-statement"},
        )
        self.assertEqual(statement.status_code, status.HTTP_200_OK, statement.data)
        total_income = next(row for row in statement.data["rows"] if row["item"] == "Total cash income")
        self.assertEqual(total_income["amount"], "600.00")

        term_two = Term.objects.create(
            academic_year=year,
            term="2",
            start_date=date(2026, 5, 18),
            end_date=date(2026, 8, 21),
            is_current=True,
        )
        target_class = AcademicClass.objects.get(academic_year=year, term=term_two, Class=class_record)
        target_bill = StudentBill.objects.get(student=student, academic_class=target_class)
        self.assertEqual(target_bill.balance, Decimal("900"))
        self.assertFalse(StudentCredit.objects.filter(student=student, amount__gt=0, is_applied=False).exists())


class OutboundCommunicationAcceptanceTests(APITestCase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="school@example.test")
    def test_report_notice_can_be_delivered_by_configured_email_channel(self):
        year, term, section, class_record, stream, teacher, academic_class, class_stream = academic_fixture("MSG", fee=100)
        student = create_student(
            name="Message Learner", reg_no="MSG-001", year=year, term=term,
            class_record=class_record, stream=stream, contact="0700000501",
        )
        preference = student.communication_preference if hasattr(student, "communication_preference") else None
        if preference is None:
            from app.models import CommunicationPreference
            preference = CommunicationPreference.objects.create(
                student=student,
                email_enabled=True,
                guardian_email="parent@example.test",
                consent_recorded_at=date(2026, 1, 1),
            )
        else:
            preference.email_enabled = True
            preference.guardian_email = "parent@example.test"
            preference.save(update_fields=["email_enabled", "guardian_email"])

        delivered = send_report_ready_notice(
            student,
            channel=OutboundMessage.CHANNEL_EMAIL,
            portal_url="https://school.example.test/parent",
        )
        self.assertEqual(delivered.status, OutboundMessage.STATUS_SENT)
        self.assertEqual(delivered.recipient, "parent@example.test")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Parent Portal", mail.outbox[0].body)
