from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from app.models import ClassBill, StudentBillItem


@receiver(post_save, sender=StudentBillItem)
def enforce_student_fee_plan(sender, instance, created, **kwargs):
    """Align generated bill-item amounts with the student's Day/Boarding plan."""
    bill = instance.bill
    student = bill.student
    academic_class = bill.academic_class

    item_name = str(getattr(instance.bill_item, "item_name", "") or "").strip().lower()
    if item_name == "school fees":
        expected = Decimal(str(academic_class.fee_amount_for_student(student) or 0))
        if Decimal(instance.amount) != expected:
            StudentBillItem.objects.filter(pk=instance.pk).update(amount=expected)
        return

    policies = ClassBill.objects.filter(
        academic_class=academic_class,
        bill_item=instance.bill_item,
    )
    if not policies.exists():
        return

    allowed = policies.filter(
        applies_to__in=[ClassBill.APPLIES_ALL, student.residency_status]
    ).exists()
    if not allowed and Decimal(instance.amount) != Decimal("0"):
        StudentBillItem.objects.filter(pk=instance.pk).update(amount=Decimal("0"))
