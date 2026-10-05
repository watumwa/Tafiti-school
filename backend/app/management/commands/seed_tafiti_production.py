from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from app.models.accounts import StaffAccount
from app.models.classes import (
    AcademicClass,
    AcademicClassStream,
    Class,
    ClassSubjectAllocation,
    Stream,
    Term,
)
from app.models.fees_payment import BillItem, ClassBill
from app.models.school_settings import AcademicYear, SchoolSetting, Section
from app.models.staffs import Role, Staff
from app.models.students import ClassRegister, Student
from app.models.subjects import Subject


class Command(BaseCommand):
    help = "Create the initial Tafiti School production dataset."

    @transaction.atomic
    def handle(self, *args, **options):
        password = "123"
        User = get_user_model()

        school = SchoolSetting.load()
        school.school_name = "Tafiti School"
        school.school_motto = "Learning for a brighter future"
        school.country = "Uganda"
        school.city = "Kampala"
        school.address = "Tafiti School"
        school.app_name = "Tafiti School"
        school.offers_primary = True
        school.offers_secondary_lower = False
        school.offers_secondary_upper = False
        school.education_level = SchoolSetting.EducationLevel.PRIMARY
        school.save()

        year, _ = AcademicYear.objects.get_or_create(academic_year="2026")
        AcademicYear.objects.exclude(pk=year.pk).update(is_current=False)
        year.is_current = True
        year.save(update_fields=("is_current",))

        term, _ = Term.objects.get_or_create(
            academic_year=year,
            term="3",
            defaults={
                "start_date": date(2026, 9, 1),
                "end_date": date(2026, 12, 5),
            },
        )
        Term.objects.filter(academic_year=year).exclude(pk=term.pk).update(is_current=False)
        term.start_date = date(2026, 9, 1)
        term.end_date = date(2026, 12, 5)
        term.is_current = True
        term.save(update_fields=("start_date", "end_date", "is_current"))

        sections = {
            "lower": Section.objects.get_or_create(section_name="Lower Primary")[0],
            "upper": Section.objects.get_or_create(section_name="Upper Primary")[0],
        }
        stream = Stream.objects.get_or_create(stream="Main")[0]

        staff_data = [
            ("Moses", "Kato", "Head master", "moses.kato"),
            ("Sarah", "Namukasa", "Director of Studies", "sarah.namukasa"),
            ("Peter", "Ochieng", "Class Teacher", "peter.ochieng"),
            ("Grace", "Nankya", "Class Teacher", "grace.nankya"),
            ("John", "Mugisha", "Class Teacher", "john.mugisha"),
            ("Esther", "Achieng", "Class Teacher", "esther.achieng"),
            ("David", "Ssemanda", "Class Teacher", "david.ssemanda"),
        ]
        staff_members = []
        for first_name, last_name, role_name, username in staff_data:
            role, _ = Role.objects.get_or_create(name=role_name)
            email = f"{username}@tafiti.school"
            staff, _ = Staff.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "birth_date": date(1985, 1, 1),
                    "gender": "M" if first_name in {"Moses", "Peter", "John", "David"} else "F",
                    "address": "Kampala, Uganda",
                    "marital_status": "M",
                    "contacts": "0700000000",
                    "qualification": "Diploma in Education",
                    "hire_date": date(2020, 1, 1),
                    "department": "Academic",
                    "salary": Decimal("800000.00"),
                    "is_academic_staff": True,
                    "staff_status": "Active",
                    "staff_photo": "Staff/Profile_pics/default.jpg",
                },
            )
            staff.first_name = first_name
            staff.last_name = last_name
            staff.is_academic_staff = True
            staff.staff_status = "Active"
            staff.save(update_fields=("first_name", "last_name", "is_academic_staff", "staff_status"))
            staff.roles.add(role)

            user, _ = User.objects.get_or_create(username=username, defaults={"email": email})
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.is_staff = True
            user.set_password(password)
            user.save()
            StaffAccount.objects.update_or_create(
                staff=staff,
                defaults={"user": user, "role": role},
            )
            staff_members.append(staff)

        class_names = [
            ("P1", "Primary One", "lower"),
            ("P2", "Primary Two", "lower"),
            ("P3", "Primary Three", "lower"),
            ("P4", "Primary Four", "upper"),
            ("P5", "Primary Five", "upper"),
            ("P6", "Primary Six", "upper"),
            ("P7", "Primary Seven", "upper"),
        ]
        academic_classes = []
        for index, (code, name, section_key) in enumerate(class_names):
            section = sections[section_key]
            school_class, _ = Class.objects.get_or_create(
                code=code,
                defaults={"name": name, "section": section},
            )
            school_class.name = name
            school_class.section = section
            school_class.save(update_fields=("name", "section"))
            academic_class, _ = AcademicClass.objects.get_or_create(
                Class=school_class,
                academic_year=year,
                term=term,
                defaults={"section": section, "fees_amount": 400000},
            )
            academic_class.section = section
            academic_class.fees_amount = 400000
            academic_class.save(update_fields=("section", "fees_amount"))
            class_stream, _ = AcademicClassStream.objects.update_or_create(
                academic_class=academic_class,
                stream=stream,
                defaults={"class_teacher": staff_members[index]},
            )
            academic_classes.append((school_class, academic_class, class_stream))

        subject_names = [
            ("MAT", "Math"),
            ("ENG", "English"),
            ("SST", "Social Studies"),
            ("SCI", "Science"),
            ("ART", "Drawing"),
            ("REA", "Reading"),
        ]
        subjects_by_section = {}
        for section_key, section in sections.items():
            subjects_by_section[section_key] = []
            for code, name in subject_names:
                subject, _ = Subject.objects.get_or_create(
                    code=f"{code}-{section_key[:1].upper()}",
                    defaults={
                        "name": name,
                        "credit_hours": 4,
                        "section": section,
                        "type": "Core",
                    },
                )
                subject.name = name
                subject.section = section
                subject.type = "Core"
                subject.credit_hours = 4
                subject.save(update_fields=("name", "section", "type", "credit_hours"))
                subjects_by_section[section_key].append(subject)

        for _, academic_class, class_stream in academic_classes:
            section_key = "lower" if academic_class.section_id == sections["lower"].pk else "upper"
            for subject_index, subject in enumerate(subjects_by_section[section_key]):
                ClassSubjectAllocation.objects.update_or_create(
                    academic_class_stream=class_stream,
                    subject=subject,
                    defaults={"subject_teacher": staff_members[subject_index % len(staff_members)], "is_active": True},
                )

        fee_items = {
            "school": BillItem.objects.get_or_create(
                item_name="School Fees",
                defaults={
                    "category": "Tuition",
                    "bill_duration": "Termly",
                    "description": "Primary school fees for Term 3, 2026",
                },
            )[0],
            "transport": BillItem.objects.get_or_create(
                item_name="Transport",
                defaults={
                    "category": "Transport",
                    "bill_duration": "Termly",
                    "description": "School transport for Term 3, 2026",
                },
            )[0],
        }
        for _, academic_class, _ in academic_classes:
            ClassBill.objects.update_or_create(
                academic_class=academic_class,
                bill_item=fee_items["school"],
                defaults={"amount": Decimal("400000.00")},
            )
            ClassBill.objects.update_or_create(
                academic_class=academic_class,
                bill_item=fee_items["transport"],
                defaults={"amount": Decimal("150000.00")},
            )

        student_names = [
            ("Brian", "M"), ("Aisha", "F"), ("Daniel", "M"), ("Maria", "F"), ("Isaac", "M"),
            ("Immaculate", "F"), ("Joseph", "M"), ("Shamim", "F"), ("Ronald", "M"), ("Mercy", "F"),
            ("Samuel", "M"), ("Doreen", "F"), ("Patrick", "M"), ("Nabirye", "F"), ("Andrew", "M"),
        ]
        for index, (first_name, gender) in enumerate(student_names, start=1):
            school_class, _, class_stream = academic_classes[(index - 1) % len(academic_classes)]
            student, _ = Student.objects.get_or_create(
                reg_no=f"TAF{index:04d}",
                defaults={
                    "student_name": f"{first_name} {['Kato', 'Namirembe', 'Mugisha', 'Atim', 'Okello'][index % 5]}",
                    "gender": gender,
                    "birthdate": date(2013 + ((index - 1) % 7), 2, min(index + 1, 28)),
                    "nationality": "Ugandan",
                    "religion": "Protestant" if index % 3 else "Muslim",
                    "address": "Kampala, Uganda",
                    "guardian": f"Guardian {index}",
                    "relationship": "Parent",
                    "contact": f"070100{index:04d}",
                    "academic_year": year,
                    "current_class": school_class,
                    "stream": stream,
                    "term": term,
                },
            )
            student.current_class = school_class
            student.academic_year = year
            student.stream = stream
            student.term = term
            student.save(update_fields=("current_class", "academic_year", "stream", "term"))
            ClassRegister.objects.get_or_create(academic_class_stream=class_stream, student=student)

        self.stdout.write(self.style.SUCCESS("Tafiti School production data seeded successfully."))
        self.stdout.write("Staff usernames: moses.kato, sarah.namukasa, peter.ochieng, grace.nankya, john.mugisha, esther.achieng, david.ssemanda")
        self.stdout.write("Temporary password for generated staff: 123")
        self.stdout.write("Students created: 15 | Classes: P1-P7 | Current term: 2026 Term 3")
