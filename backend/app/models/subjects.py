from django.db import models
from django.urls import reverse

class Subject(models.Model):

    code = models.CharField(max_length=10)
    name = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)
    credit_hours = models.IntegerField()
    section = models.ForeignKey("app.Section", on_delete=models.CASCADE)
    type = models.CharField(max_length=50, choices=[("Core", "Core"), ("Elective", "Elective")])
    show_on_report = models.BooleanField(
        default=True,
        help_text="Show this subject on report cards even when it is excluded from totals.",
    )
    include_in_totals = models.BooleanField(
        default=True,
        help_text="Include this subject's score in total/average computations.",
    )
    calculate_grade = models.BooleanField(
        default=True,
        help_text="Calculate and display a grade for this subject.",
    )
    include_in_ranking = models.BooleanField(
        default=True,
        help_text="Use this subject when computing class positions/rankings.",
    )

    class Meta:
        verbose_name = ("Subject")
        verbose_name_plural = ("Subjects")

    def __str__(self):
        # Section context is essential where the same curriculum subject exists
        # at different school levels (for example lower- and upper-primary English).
        return f"{self.name} — {self.section}"

    @property
    def is_report_only(self):
        return self.show_on_report and not self.include_in_totals

    def get_absolute_url(self):
        return reverse("Subject_detail", kwargs={"pk": self.pk})
