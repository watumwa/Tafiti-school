from datetime import date

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.models import (
    AcademicClass,
    AcademicClassStream,
    AcademicYear,
    Class,
    ClassRegister,
    Section,
    Staff,
    Stream,
    Student,
    StudentPromotionHistory,
    Term,
)


class ClassesWorkspaceTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="classes-admin",
            email="classes-admin@example.test",
            password="test-password",
        )
        self.client.force_authenticate(user=self.admin)
        self.section = Section.objects.create(section_name="Classes Workspace")
        self.year = AcademicYear.objects.create(academic_year="2026", is_current=True)
        self.next_year = AcademicYear.objects.create(academic_year="2027", is_current=False)
        self.term_three = Term.objects.create(
            academic_year=self.year,
            term="3",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 31),
            is_current=True,
        )
        self.next_term = Term.objects.create(
            academic_year=self.next_year,
            term="1",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 4, 30),
            is_current=False,
        )
        self.teacher = Staff.objects.create(
            first_name="Class",
            last_name="Teacher",
            birth_date=date(1990, 1, 1),
            gender="M",
            address="School",
            marital_status="U",
            contacts="0700123456",
            email="classes-teacher@example.test",
            qualification="Diploma",
            hire_date=date(2020, 1, 1),
            department="Academic",
            salary=1,
            staff_status="Active",
            staff_photo=SimpleUploadedFile("classes-teacher.jpg", b"img", content_type="image/jpeg"),
        )
        self.source_school_class = Class.objects.create(name="Primary Three", code="P3", section=self.section)
        self.target_school_class = Class.objects.create(name="Primary Four", code="P4", section=self.section)
        self.source_stream = Stream.objects.create(stream="Blue")
        self.target_stream = self.source_stream
        self.source_class = AcademicClass.objects.create(
            section=self.section,
            Class=self.source_school_class,
            academic_year=self.year,
            term=self.term_three,
            fees_amount=0,
        )
        self.target_class = AcademicClass.objects.create(
            section=self.section,
            Class=self.target_school_class,
            academic_year=self.next_year,
            term=self.next_term,
            fees_amount=0,
        )
        self.source_class_stream = AcademicClassStream.objects.create(
            academic_class=self.source_class,
            stream=self.source_stream,
            class_teacher=self.teacher,
        )
        AcademicClassStream.objects.create(
            academic_class=self.target_class,
            stream=self.target_stream,
            class_teacher=self.teacher,
        )

    def url(self, action):
        return reverse(
            "api_workspace_classes_action",
            kwargs={"pk": self.source_class.pk, "action": action},
        )

    def test_registers_new_student_in_selected_class_stream(self):
        response = self.client.post(
            self.url("register"),
            {
                "academic_class_stream": self.source_class_stream.pk,
                "student_name": "New Classes Learner",
                "gender": "F",
                "birthdate": "2016-02-03",
                "nationality": "Ugandan",
                "religion": "Protestant",
                "address": "Kampala",
                "guardian": "Learner Guardian",
                "relationship": "Parent",
                "contact": "0700111000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        student = Student.objects.get(student_name="New Classes Learner")
        self.assertEqual(student.current_class, self.source_school_class)
        self.assertEqual(student.stream, self.source_stream)
        self.assertTrue(ClassRegister.objects.filter(
            student=student,
            academic_class_stream=self.source_class_stream,
        ).exists())

    def test_promotes_registered_students_using_existing_promotion_service(self):
        student = Student.objects.create(
            reg_no="CLS-001",
            student_name="Promoted Classes Learner",
            gender="F",
            birthdate=date(2015, 1, 1),
            nationality="Ugandan",
            religion="Protestant",
            address="Kampala",
            guardian="Learner Guardian",
            relationship="Parent",
            contact="0700222000",
            academic_year=self.year,
            current_class=self.source_school_class,
            stream=self.source_stream,
            term=self.term_three,
        )
        ClassRegister.objects.create(
            academic_class_stream=self.source_class_stream,
            student=student,
        )

        response = self.client.post(
            self.url("promote"),
            {"target_academic_class": self.target_class.pk, "active_students_only": "true"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(ClassRegister.objects.filter(
            student=student,
            academic_class_stream__academic_class=self.target_class,
        ).exists())
        student.refresh_from_db()
        self.assertEqual(student.current_class, self.target_school_class)
        self.assertEqual(response.data["promoted_count"], 1)
        self.assertEqual(StudentPromotionHistory.objects.count(), 1)
