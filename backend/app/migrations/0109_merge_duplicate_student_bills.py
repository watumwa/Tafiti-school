from django.db import migrations, models
from django.db.models import Count, Sum


def merge_duplicate_student_bills(apps, schema_editor):
    StudentBill = apps.get_model("app", "StudentBill")
    StudentBillItem = apps.get_model("app", "StudentBillItem")
    Payment = apps.get_model("app", "Payment")
    StudentCredit = apps.get_model("app", "StudentCredit")
    StudentDocument = apps.get_model("app", "StudentDocument")

    duplicate_groups = list(
        StudentBill.objects.values("student_id", "academic_class_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )

    for group in duplicate_groups:
        bills = list(
            StudentBill.objects.filter(
                student_id=group["student_id"],
                academic_class_id=group["academic_class_id"],
            ).order_by("id")
        )
        canonical = bills[0]

        due_dates = [bill.due_date for bill in bills if bill.due_date]
        had_overdue_bill = any(bill.status == "Overdue" for bill in bills)

        for duplicate in bills[1:]:
            # Payments and supporting records are history and must never be discarded.
            Payment.objects.filter(bill_id=duplicate.id).update(bill_id=canonical.id)
            StudentCredit.objects.filter(original_bill_id=duplicate.id).update(
                original_bill_id=canonical.id
            )
            StudentCredit.objects.filter(applied_to_bill_id=duplicate.id).update(
                applied_to_bill_id=canonical.id
            )
            StudentDocument.objects.filter(bill_id=duplicate.id).update(bill_id=canonical.id)

            # Repeated system charges are the duplication defect. Keep the canonical
            # charge, but retain charge types that only existed on the duplicate bill.
            for item in StudentBillItem.objects.filter(bill_id=duplicate.id).order_by("id"):
                existing = StudentBillItem.objects.filter(
                    bill_id=canonical.id,
                    bill_item_id=item.bill_item_id,
                ).order_by("id").first()
                if existing:
                    item.delete()
                else:
                    item.bill_id = canonical.id
                    item.save(update_fields=["bill"])

            duplicate.delete()

        if due_dates:
            canonical.due_date = min(due_dates)

        charges = (
            StudentBillItem.objects.filter(bill_id=canonical.id).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        payments = (
            Payment.objects.filter(bill_id=canonical.id).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        applied_credits = (
            StudentCredit.objects.filter(applied_to_bill_id=canonical.id, amount__lt=0)
            .aggregate(total=Sum("amount"))["total"]
            or 0
        )
        balance = charges - payments + applied_credits
        canonical.status = "Paid" if balance <= 0 else ("Overdue" if had_overdue_bill else "Unpaid")
        canonical.save(update_fields=["due_date", "status"])

class Migration(migrations.Migration):
    dependencies = [("app", "0108_remove_student_student_number")]

    operations = [
        migrations.RunPython(merge_duplicate_student_bills, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="studentbill",
            constraint=models.UniqueConstraint(
                fields=("student", "academic_class"),
                name="unique_student_bill_per_academic_class",
            ),
        ),
    ]
