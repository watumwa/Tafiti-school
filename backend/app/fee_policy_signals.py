from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from app.models import AcademicClass, ClassBill, StudentBill, StudentBillItem, Term


def _selected_class_bill(academic_class, bill_item, student):
    policy = ClassBill.objects.filter(
        academic_class=academic_class,
        bill_item=bill_item,
    ).first()
    if not policy:
        return None
    return policy if policy.applies_to_student(student) else None


def _sync_bill_item(instance):
    bill = instance.bill
    student = bill.student
    academic_class = bill.academic_class
    item_name = str(getattr(instance.bill_item, "item_name", "") or "").strip().lower()

    if item_name == "school fees":
        expected = Decimal(str(academic_class.fee_amount_for_student(student) or 0))
    else:
        selected = _selected_class_bill(academic_class, instance.bill_item, student)
        expected = Decimal(str(selected.amount if selected else 0))

    if Decimal(instance.amount) != expected:
        StudentBillItem.objects.filter(pk=instance.pk).update(amount=expected)


def _sync_student_bill(bill):
    for item in bill.items.select_related("bill_item").all():
        _sync_bill_item(item)


def _previous_term(term):
    return (
        Term.objects.filter(
            academic_year=term.academic_year,
            end_date__lt=term.start_date,
        )
        .exclude(pk=term.pk)
        .order_by("-end_date", "-id")
        .first()
    )


@receiver(post_save, sender=StudentBillItem)
def enforce_student_fee_plan(sender, instance, created, **kwargs):
    """Align every generated bill item with the student's Day/Boarding fee plan."""
    _sync_bill_item(instance)


@receiver(post_save, sender=ClassBill)
def resync_existing_bills_when_fee_policy_changes(sender, instance, **kwargs):
    """Apply a changed class fee policy to existing bills in that class/term."""
    for bill in StudentBill.objects.filter(academic_class=instance.academic_class).select_related("student"):
        _sync_student_bill(bill)


@receiver(post_save, sender=Term)
def copy_residency_fee_policy_to_new_term(sender, instance, **kwargs):
    """Complete the normal term rollover with Day/Boarding fee-plan details."""
    if not instance.is_current:
        return

    source_term = _previous_term(instance)
    if not source_term:
        return

    target_classes = AcademicClass.objects.filter(
        academic_year=instance.academic_year,
        term=instance,
    ).select_related("Class", "section")

    for target in target_classes:
        source = AcademicClass.objects.filter(
            academic_year=instance.academic_year,
            term=source_term,
            Class=target.Class,
            section=target.section,
        ).first()
        if not source:
            continue

        update_fields = []
        if target.day_fees_amount != source.day_fees_amount:
            target.day_fees_amount = source.day_fees_amount
            update_fields.append("day_fees_amount")
        if target.boarding_fees_amount != source.boarding_fees_amount:
            target.boarding_fees_amount = source.boarding_fees_amount
            update_fields.append("boarding_fees_amount")
        if update_fields:
            target.save(update_fields=update_fields)

        for source_policy in ClassBill.objects.filter(academic_class=source).select_related("bill_item"):
            ClassBill.objects.update_or_create(
                academic_class=target,
                bill_item=source_policy.bill_item,
                defaults={
                    "amount": source_policy.amount,
                    "applies_to": source_policy.applies_to,
                },
            )

        for bill in StudentBill.objects.filter(academic_class=target).select_related("student"):
            _sync_student_bill(bill)
