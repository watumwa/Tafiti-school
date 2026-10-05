from django.db import migrations, models
from django.db.models import Sum


def _identity_key(student):
    name = " ".join(str(student.student_name or "").casefold().split())
    contact = "".join(
        character for character in str(student.contact or "") if character.isalnum()
    ).casefold()
    if not name or not student.birthdate or not contact:
        return None
    return name, student.birthdate, contact


def _move_unique_rows(Model, student_field, duplicate_id, canonical_id, unique_fields):
    """Move rows to the canonical student, dropping only relational duplicates."""
    student_id_field = f"{student_field}_id"
    for row in Model.objects.filter(**{student_id_field: duplicate_id}).order_by("id"):
        lookup = {student_id_field: canonical_id}
        for field_name in unique_fields:
            field = Model._meta.get_field(field_name)
            lookup[field.attname] = getattr(row, field.attname)

        if Model.objects.filter(**lookup).exists():
            row.delete()
        else:
            setattr(row, student_id_field, canonical_id)
            row.save(update_fields=[student_field])


def _merge_bill(apps, source_bill, target_bill):
    StudentBillItem = apps.get_model("app", "StudentBillItem")
    Payment = apps.get_model("app", "Payment")
    StudentCredit = apps.get_model("app", "StudentCredit")
    StudentDocument = apps.get_model("app", "StudentDocument")

    Payment.objects.filter(bill_id=source_bill.id).update(bill_id=target_bill.id)
    StudentCredit.objects.filter(original_bill_id=source_bill.id).update(
        original_bill_id=target_bill.id
    )
    StudentCredit.objects.filter(applied_to_bill_id=source_bill.id).update(
        applied_to_bill_id=target_bill.id
    )
    StudentDocument.objects.filter(bill_id=source_bill.id).update(bill_id=target_bill.id)

    for item in StudentBillItem.objects.filter(bill_id=source_bill.id).order_by("id"):
        existing = StudentBillItem.objects.filter(
            bill_id=target_bill.id,
            bill_item_id=item.bill_item_id,
        ).order_by("id").first()
        if existing:
            item.delete()
        else:
            item.bill_id = target_bill.id
            item.save(update_fields=["bill"])

    due_dates = [value for value in (target_bill.due_date, source_bill.due_date) if value]
    if due_dates:
        target_bill.due_date = min(due_dates)
    had_overdue_bill = target_bill.status == "Overdue" or source_bill.status == "Overdue"
    source_bill.delete()

    charges = (
        StudentBillItem.objects.filter(bill_id=target_bill.id).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    payments = (
        Payment.objects.filter(bill_id=target_bill.id).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    applied_credits = (
        StudentCredit.objects.filter(applied_to_bill_id=target_bill.id, amount__lt=0)
        .aggregate(total=Sum("amount"))["total"]
        or 0
    )
    balance = charges - payments + applied_credits
    target_bill.status = "Paid" if balance <= 0 else ("Overdue" if had_overdue_bill else "Unpaid")
    target_bill.save(update_fields=["due_date", "status"])


def _merge_student(apps, canonical, duplicate):
    ClassRegister = apps.get_model("app", "ClassRegister")
    StudentBill = apps.get_model("app", "StudentBill")
    StudentDocument = apps.get_model("app", "StudentDocument")
    StudentCredit = apps.get_model("app", "StudentCredit")
    FinancialNotification = apps.get_model("app", "FinancialNotification")
    Result = apps.get_model("app", "Result")
    ReportResults = apps.get_model("app", "ReportResults")
    ReportRemark = apps.get_model("app", "ReportRemark")
    ReportCycleRemark = apps.get_model("app", "ReportCycleRemark")
    TermResult = apps.get_model("app", "TermResult")
    AnnualResult = apps.get_model("app", "AnnualResult")
    AttendanceRecord = apps.get_model("app", "AttendanceRecord")
    ParentAccess = apps.get_model("app", "ParentAccess")
    ParentPortalAudit = apps.get_model("app", "ParentPortalAudit")
    ParentNotification = apps.get_model("app", "ParentNotification")
    ParentConversation = apps.get_model("app", "ParentConversation")
    AdmissionApplication = apps.get_model("app", "AdmissionApplication")
    LibraryLoan = apps.get_model("app", "LibraryLoan")

    _move_unique_rows(
        ClassRegister,
        "student",
        duplicate.id,
        canonical.id,
        ("academic_class_stream",),
    )

    for source_bill in StudentBill.objects.filter(student_id=duplicate.id).order_by("id"):
        target_bill = StudentBill.objects.filter(
            student_id=canonical.id,
            academic_class_id=source_bill.academic_class_id,
        ).order_by("id").first()
        if target_bill:
            _merge_bill(apps, source_bill, target_bill)
        else:
            source_bill.student_id = canonical.id
            source_bill.save(update_fields=["student"])

    _move_unique_rows(Result, "student", duplicate.id, canonical.id, ("assessment",))
    _move_unique_rows(ReportRemark, "student", duplicate.id, canonical.id, ("term",))
    _move_unique_rows(
        ReportCycleRemark,
        "student",
        duplicate.id,
        canonical.id,
        ("academic_class", "scope_key"),
    )
    _move_unique_rows(AttendanceRecord, "student", duplicate.id, canonical.id, ("session",))
    _move_unique_rows(ParentAccess, "student", duplicate.id, canonical.id, ("user",))
    _move_unique_rows(
        ParentConversation,
        "student",
        duplicate.id,
        canonical.id,
        ("parent", "staff"),
    )

    # These relations do not become ambiguous when their student is replaced.
    StudentDocument.objects.filter(student_id=duplicate.id).update(student_id=canonical.id)
    StudentCredit.objects.filter(student_id=duplicate.id).update(student_id=canonical.id)
    FinancialNotification.objects.filter(recipient_id=duplicate.id).update(recipient_id=canonical.id)
    ReportResults.objects.filter(student_id=duplicate.id).update(student_id=canonical.id)
    TermResult.objects.filter(student_id=duplicate.id).update(student_id=canonical.id)
    AnnualResult.objects.filter(student_id=duplicate.id).update(student_id=canonical.id)
    ParentPortalAudit.objects.filter(student_id=duplicate.id).update(student_id=canonical.id)
    ParentNotification.objects.filter(student_id=duplicate.id).update(student_id=canonical.id)
    LibraryLoan.objects.filter(student_id=duplicate.id).update(student_id=canonical.id)

    # Preserve admission history while satisfying its one-to-one student link.
    canonical_application = AdmissionApplication.objects.filter(
        enrolled_student_id=canonical.id
    ).first()
    for application in AdmissionApplication.objects.filter(enrolled_student_id=duplicate.id):
        if canonical_application:
            application.enrolled_student_id = None
        else:
            application.enrolled_student_id = canonical.id
            canonical_application = application
        application.save(update_fields=["enrolled_student"])

    if duplicate.is_active and not canonical.is_active:
        canonical.is_active = True
        canonical.save(update_fields=["is_active"])

    duplicate.delete()


def merge_duplicate_students(apps, schema_editor):
    Student = apps.get_model("app", "Student")
    grouped_students = {}
    for student in Student.objects.all().order_by("id"):
        key = _identity_key(student)
        if key is not None:
            grouped_students.setdefault(key, []).append(student)

    for students in grouped_students.values():
        if len(students) < 2:
            continue
        canonical = students[0]
        for duplicate in students[1:]:
            _merge_student(apps, canonical, duplicate)


class Migration(migrations.Migration):
    dependencies = [("app", "0118_alter_announcement_audience_alter_event_audience_and_more")]

    operations = [
        migrations.RunPython(merge_duplicate_students, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="student",
            constraint=models.UniqueConstraint(
                fields=("student_name", "birthdate", "contact"),
                name="unique_student_identity",
            ),
        ),
    ]
