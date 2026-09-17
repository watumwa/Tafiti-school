from django.db import migrations
from django.db.models import F, Sum


def _recalculate_bill_status(StudentBillItem, Payment, StudentCredit, bill):
    charges = (
        StudentBillItem.objects.filter(bill_id=bill.id).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    payments = (
        Payment.objects.filter(bill_id=bill.id).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    credits = (
        StudentCredit.objects.filter(applied_to_bill_id=bill.id, amount__lt=0)
        .aggregate(total=Sum("amount"))["total"]
        or 0
    )
    bill.status = "Paid" if charges - payments + credits <= 0 else "Unpaid"
    bill.save(update_fields=["status"])


def repair_cross_year_academic_classes(apps, schema_editor):
    AcademicClass = apps.get_model("app", "AcademicClass")
    AcademicClassStream = apps.get_model("app", "AcademicClassStream")
    Assessment = apps.get_model("app", "Assessment")
    ClassBill = apps.get_model("app", "ClassBill")
    ClassRegister = apps.get_model("app", "ClassRegister")
    ClassSubjectAllocation = apps.get_model("app", "ClassSubjectAllocation")
    Timetable = apps.get_model("app", "Timetable")
    AttendanceSession = apps.get_model("app", "AttendanceSession")
    StudentBill = apps.get_model("app", "StudentBill")
    StudentBillItem = apps.get_model("app", "StudentBillItem")
    Payment = apps.get_model("app", "Payment")
    StudentCredit = apps.get_model("app", "StudentCredit")
    StudentDocument = apps.get_model("app", "StudentDocument")
    AnnualResult = apps.get_model("app", "AnnualResult")
    TermResult = apps.get_model("app", "TermResult")
    ReportResults = apps.get_model("app", "ReportResults")
    StudentPromotionHistory = apps.get_model("app", "StudentPromotionHistory")

    mismatches = list(
        AcademicClass.objects.exclude(academic_year_id=F("term__academic_year_id"))
        .select_related("term")
        .order_by("id")
    )

    # Refuse to cascade-delete academic history that needs human conflict resolution.
    for source in mismatches:
        if Assessment.objects.filter(academic_class_id=source.id).exists():
            raise RuntimeError(f"AcademicClass {source.id} has assessments and cannot be repaired automatically.")
        if AnnualResult.objects.filter(academic_class_id=source.id).exists():
            raise RuntimeError(f"AcademicClass {source.id} has annual results and cannot be repaired automatically.")
        if TermResult.objects.filter(academic_class_id=source.id).exists():
            raise RuntimeError(f"AcademicClass {source.id} has term results and cannot be repaired automatically.")
        if ReportResults.objects.filter(academic_class_id=source.id).exists():
            raise RuntimeError(f"AcademicClass {source.id} has report results and cannot be repaired automatically.")

        source_streams = AcademicClassStream.objects.filter(academic_class_id=source.id)
        if ClassRegister.objects.filter(academic_class_stream__in=source_streams).exists():
            raise RuntimeError(f"AcademicClass {source.id} has class registers and cannot be repaired automatically.")
        if ClassSubjectAllocation.objects.filter(academic_class_stream__in=source_streams).exists():
            raise RuntimeError(f"AcademicClass {source.id} has subject allocations and cannot be repaired automatically.")
        if Timetable.objects.filter(class_stream__in=source_streams).exists():
            raise RuntimeError(f"AcademicClass {source.id} has timetables and cannot be repaired automatically.")
        if AttendanceSession.objects.filter(class_stream__in=source_streams).exists():
            raise RuntimeError(f"AcademicClass {source.id} has attendance and cannot be repaired automatically.")

    for source in mismatches:
        correct_year_id = source.term.academic_year_id
        target = (
            AcademicClass.objects.filter(
                Class_id=source.Class_id,
                academic_year_id=correct_year_id,
                term_id=source.term_id,
            )
            .exclude(id=source.id)
            .order_by("id")
            .first()
        )

        if not target:
            source.academic_year_id = correct_year_id
            source.save(update_fields=["academic_year"])
            continue

        for source_bill in StudentBill.objects.filter(academic_class_id=source.id).order_by("id"):
            target_bill = StudentBill.objects.filter(
                student_id=source_bill.student_id,
                academic_class_id=target.id,
            ).order_by("id").first()
            if not target_bill:
                source_bill.academic_class_id = target.id
                source_bill.save(update_fields=["academic_class"])
                continue

            Payment.objects.filter(bill_id=source_bill.id).update(bill_id=target_bill.id)
            StudentCredit.objects.filter(original_bill_id=source_bill.id).update(
                original_bill_id=target_bill.id
            )
            StudentCredit.objects.filter(applied_to_bill_id=source_bill.id).update(
                applied_to_bill_id=target_bill.id
            )
            StudentDocument.objects.filter(bill_id=source_bill.id).update(bill_id=target_bill.id)

            for item in StudentBillItem.objects.filter(bill_id=source_bill.id).order_by("id"):
                exact_duplicate = StudentBillItem.objects.filter(
                    bill_id=target_bill.id,
                    bill_item_id=item.bill_item_id,
                    description=item.description,
                    amount=item.amount,
                    charge_date=item.charge_date,
                    fee_category=item.fee_category,
                    notes=item.notes,
                ).exists()
                if exact_duplicate:
                    item.delete()
                else:
                    item.bill_id = target_bill.id
                    item.save(update_fields=["bill"])

            source_bill.delete()
            _recalculate_bill_status(StudentBillItem, Payment, StudentCredit, target_bill)

        for source_class_bill in ClassBill.objects.filter(academic_class_id=source.id):
            if ClassBill.objects.filter(
                academic_class_id=target.id,
                bill_item_id=source_class_bill.bill_item_id,
            ).exists():
                source_class_bill.delete()
            else:
                source_class_bill.academic_class_id = target.id
                source_class_bill.save(update_fields=["academic_class"])

        StudentPromotionHistory.objects.filter(source_academic_class_id=source.id).update(
            source_academic_class_id=target.id
        )
        StudentPromotionHistory.objects.filter(target_academic_class_id=source.id).update(
            target_academic_class_id=target.id
        )
        StudentPromotionHistory.objects.filter(
            source_stream__academic_class_id=source.id
        ).update(source_stream_id=None)

        # The safety checks above guarantee these source streams contain no history.
        AcademicClassStream.objects.filter(academic_class_id=source.id).delete()
        source.delete()


class Migration(migrations.Migration):
    dependencies = [("app", "0109_merge_duplicate_student_bills")]

    operations = [
        migrations.RunPython(repair_cross_year_academic_classes, migrations.RunPython.noop),
    ]
