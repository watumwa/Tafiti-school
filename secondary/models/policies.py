from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class SecondaryComputationPolicy(models.Model):
    class Level(models.TextChoices):
        LOWER_SECONDARY = "LOWER_SECONDARY", "Lower Secondary (S1-S4)"

    class RoundingMode(models.TextChoices):
        ONE_DECIMAL = "ONE_DECIMAL", "One decimal place (69.4)"
        WHOLE_NUMBER = "WHOLE_NUMBER", "Whole number (half up)"
        WHOLE_NUMBER_DOWN = "WHOLE_NUMBER_DOWN", "Whole number (floor)"

    name = models.CharField(max_length=100, default="Uganda CBC Lower Secondary")
    section = models.ForeignKey(
        "app.Section",
        on_delete=models.CASCADE,
        related_name="secondary_policies",
    )
    level = models.CharField(
        max_length=30,
        choices=Level.choices,
        default=Level.LOWER_SECONDARY,
    )
    ca_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("20.00"))
    exam_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("80.00"))
    rounding_mode = models.CharField(
        max_length=30,
        choices=RoundingMode.choices,
        default=RoundingMode.ONE_DECIMAL,
    )
    effective_from = models.DateField(default=timezone.now)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_from", "-id"]
        db_table = "app_secondarycomputationpolicy"

    def __str__(self):
        return f"{self.name} ({self.section})"

    @property
    def grade_band_count(self):
        return self.grade_bands.count()

    def clean(self):
        total_weight = (self.ca_weight or Decimal("0")) + (self.exam_weight or Decimal("0"))
        if total_weight != Decimal("100"):
            raise ValidationError("CA and exam weights must add up to exactly 100.")

        if self.ca_weight < 0 or self.exam_weight < 0:
            raise ValidationError("Weights cannot be negative.")

        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError("Effective end date cannot be earlier than effective start date.")

    @classmethod
    def get_active_policy(cls, section, level):
        today = timezone.localdate()
        return (
            cls.objects.filter(
                section=section,
                level=level,
                is_active=True,
                effective_from__lte=today,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
            .order_by("-effective_from", "-id")
            .first()
        )


class SecondaryGradeBand(models.Model):
    policy = models.ForeignKey(
        "secondary.SecondaryComputationPolicy",
        on_delete=models.CASCADE,
        related_name="grade_bands",
    )
    grade = models.CharField(max_length=5)
    descriptor = models.CharField(max_length=120)
    min_score = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "-min_score"]
        unique_together = ("policy", "grade")
        db_table = "app_secondarygradeband"

    def __str__(self):
        return f"{self.grade}: {self.min_score}-{self.max_score}"

    def clean(self):
        if self.min_score < 0 or self.max_score > 100:
            raise ValidationError("Grade band scores must be within 0 to 100.")

        if self.min_score > self.max_score:
            raise ValidationError("Minimum score cannot be greater than maximum score.")

        if not self.policy_id:
            return

        overlaps = SecondaryGradeBand.objects.filter(policy_id=self.policy_id).exclude(pk=self.pk).filter(
            min_score__lte=self.max_score,
            max_score__gte=self.min_score,
        )
        if overlaps.exists():
            raise ValidationError("Grade band overlaps with an existing range in this policy.")
