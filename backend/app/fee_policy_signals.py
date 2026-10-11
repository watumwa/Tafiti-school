from decimal import Decimal

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from app.models import AcademicClass, ClassBill, Student, StudentBill, StudentBillItem, Term


def _selected_class_bill(academic_class, bill_item, student):
    """Prefer the student's exact Day/Boarding policy, then fall back to All."""
    residency = getattr(student, "residency_status", ClassBill.APPLIES_DAY)
    policies = ClassBill.objects.filter(
        academic_class=academic_class,
        bill_item=bill_item,
    )
    return (
        policies.filter(applies_to=residency).first()
        or policies.filter(applies_to=ClassBill.APPLIES_ALL).first()
    )


def _selected_class_bills_for_student(academic_class, student):
    """Return one applicable class-bill policy per fee item for this student."""
    residency = getattr(student, "residency_status", ClassBill.APPLIES_DAY)
    selected = {}
    policies = ClassBill.objects.filter(academic_class=academic_class).select_related("bill_item").order_by("bill_item_id", "id")
    for policy in policies:
        current = selected.get(policy.bill_item_id)
        if policy.applies_to == residency:
            selected[policy.bill_item_id] = policy
        elif policy.applies_to == ClassBill.APPLIES_ALL and current is None:
            selected[policy.bill_item_id] = policy
    return list(selected.values())


def _sync_bill_item(instance):
    bill = instance.bill
    student = bill.student
    academic_class = bill.academic_class
    item_name = str(getattr(instance.bill_item, "item_name", "") or "").strip().lower()

    # Class Bill is the visible billing policy and therefore the source of
    # truth whenever a matching rule exists. An exact Day/Boarding rule wins
    # over All students. The older AcademicClass fee fields remain only as a
    # compatibility fallback for legacy School Fees records that have no
    # ClassBill policy at all.
    selected = _selected_class_bill(academic_class, instance.bill_item, student)
    if selected:
        expected = Decimal(str(selected.amount or 0))
    elif item_name == "school fees":
        expected = Decimal(str(academic_class.fee_amount_for_student(student) or 0))
    else:
        expected = Decimal("0")

    if Decimal(instance.amount) != expected:
        StudentBillItem.objects.filter(pk=instance.pk).update(amount=expected)


def _sync_student_bill(bill):
    selected_policies = _selected_class_bills_for_student(bill.academic_class, bill.student)
    selected_item_ids = {policy.bill_item_id for policy in selected_policies}

    for policy in selected_policies:
        lines = bill.items.filter(bill_item=policy.bill_item).order_by("id")
        line = lines.first()
        if line:
            if lines.count() > 1:
                lines.exclude(pk=line.pk).delete()
            if line.description != policy.bill_item.description:
                StudentBillItem.objects.filter(pk=line.pk).update(description=policy.bill_item.description)
                line.description = policy.bill_item.description
            _sync_bill_item(line)
        else:
            StudentBillItem.objects.create(
                bill=bill,
                bill_item=policy.bill_item,
                description=policy.bill_item.description,
                amount=policy.amount,
            )

    # Existing lines whose policy no longer applies are retained for audit
    # continuity but reduced to zero instead of charging the wrong student type.
    for item in bill.items.select_related("bill_item").exclude(bill_item_id__in=selected_item_ids):
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


@receiver([post_save, post_delete], sender=ClassBill)
def resync_existing_bills_when_fee_policy_changes(sender, instance, **kwargs):
    """Apply a changed class fee policy to existing bills in that class/term."""
    for bill in StudentBill.objects.filter(academic_class=instance.academic_class).select_related("student"):
        _sync_student_bill(bill)


@receiver(pre_save, sender=Student)
def remember_previous_student_residency(sender, instance, **kwargs):
    """Remember student type so a Day/Boarding change can re-price the current bill."""
    if not instance.pk:
        return
    instance._previous_residency_status = (
        Student.objects.filter(pk=instance.pk).values_list("residency_status", flat=True).first()
    )


@receiver(post_save, sender=Student)
def resync_current_bill_when_student_type_changes(sender, instance, created, **kwargs):
    """Immediately apply the correct fee policy when a learner changes Day/Boarding type."""
    if created:
        return
    previous = getattr(instance, "_previous_residency_status", None)
    if previous is None or previous == instance.residency_status:
        return

    bills = StudentBill.objects.filter(
        student=instance,
        academic_class__academic_year=instance.academic_year,
        academic_class__term=instance.term,
        academic_class__Class=instance.current_class,
    ).select_related("student", "academic_class")
    for bill in bills:
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
                applies_to=source_policy.applies_to,
                defaults={"amount": source_policy.amount},
            )

        for bill in StudentBill.objects.filter(academic_class=target).select_related("student"):
            _sync_student_bill(bill)
