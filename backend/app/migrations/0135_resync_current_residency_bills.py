from decimal import Decimal

from django.db import migrations


def resync_current_residency_bills(apps, schema_editor):
    """Repair current-term bills using exact Day/Boarding policy before All fallback."""
    ClassBill = apps.get_model("app", "ClassBill")
    StudentBill = apps.get_model("app", "StudentBill")
    StudentBillItem = apps.get_model("app", "StudentBillItem")

    bills = StudentBill.objects.filter(
        academic_class__academic_year__is_current=True,
        academic_class__term__is_current=True,
    ).select_related("student", "academic_class")

    for bill in bills.iterator():
        residency = getattr(bill.student, "residency_status", "Day") or "Day"
        policies = ClassBill.objects.filter(
            academic_class_id=bill.academic_class_id,
        ).select_related("bill_item").order_by("bill_item_id", "id")

        grouped = {}
        for policy in policies:
            choices = grouped.setdefault(policy.bill_item_id, {"exact": None, "all": None})
            if policy.applies_to == residency:
                choices["exact"] = policy
            elif policy.applies_to == "All":
                choices["all"] = policy

        for bill_item_id, choices in grouped.items():
            selected = choices["exact"] or choices["all"]
            lines = StudentBillItem.objects.filter(
                bill_id=bill.pk,
                bill_item_id=bill_item_id,
            ).order_by("id")
            line = lines.first()

            if selected is None:
                # The fee item has policies, but none apply to this learner.
                # Preserve the ledger line for audit continuity and neutralize it.
                if line:
                    lines.update(amount=Decimal("0"))
                continue

            description = selected.bill_item.description
            if line:
                lines.exclude(pk=line.pk).delete()
                StudentBillItem.objects.filter(pk=line.pk).update(
                    amount=selected.amount,
                    description=description,
                )
            else:
                StudentBillItem.objects.create(
                    bill_id=bill.pk,
                    bill_item_id=bill_item_id,
                    amount=selected.amount,
                    description=description,
                )


class Migration(migrations.Migration):
    dependencies = [("app", "0134_unstreamed_class_placeholder")]

    operations = [
        migrations.RunPython(resync_current_residency_bills, migrations.RunPython.noop),
    ]
