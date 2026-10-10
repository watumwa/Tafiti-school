from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("app", "0128_payment_mobile_money_method")]

    operations = [
        migrations.AddField(
            model_name="student",
            name="lin_number",
            field=models.CharField(blank=True, help_text="Uganda learner identification number issued by the education authorities.", max_length=40, null=True, unique=True, verbose_name="Learner Identification Number (LIN)"),
        ),
        migrations.AddField(
            model_name="student",
            name="schoolpay_number",
            field=models.CharField(blank=True, help_text="Optional student payment identifier used by SchoolPay or another school payment channel.", max_length=50, null=True, unique=True, verbose_name="SchoolPay Number"),
        ),
        migrations.AddField(
            model_name="student",
            name="residency_status",
            field=models.CharField(choices=[("Day", "Day"), ("Boarding", "Boarding")], default="Day", max_length=10, verbose_name="Student Type"),
        ),
        migrations.AddField(
            model_name="academicclass",
            name="day_fees_amount",
            field=models.IntegerField(blank=True, help_text="Optional school-fee amount for Day students in this class and term.", null=True),
        ),
        migrations.AddField(
            model_name="academicclass",
            name="boarding_fees_amount",
            field=models.IntegerField(blank=True, help_text="Optional school-fee amount for Boarding students in this class and term.", null=True),
        ),
        migrations.AlterField(
            model_name="academicclass",
            name="fees_amount",
            field=models.IntegerField(help_text="Fallback school-fee amount when a day/boarding amount is not configured."),
        ),
        migrations.AddField(
            model_name="classbill",
            name="applies_to",
            field=models.CharField(choices=[("All", "All students"), ("Day", "Day students only"), ("Boarding", "Boarding students only")], default="All", help_text="Choose whether this fee applies to all, Day only or Boarding only students.", max_length=10),
        ),
        migrations.AddField(
            model_name="subject",
            name="show_on_report",
            field=models.BooleanField(default=True, help_text="Show this subject on report cards even when it is excluded from totals."),
        ),
        migrations.AddField(
            model_name="subject",
            name="include_in_totals",
            field=models.BooleanField(default=True, help_text="Include this subject's score in total/average computations."),
        ),
        migrations.AddField(
            model_name="subject",
            name="calculate_grade",
            field=models.BooleanField(default=True, help_text="Calculate and display a grade for this subject."),
        ),
        migrations.AddField(
            model_name="subject",
            name="include_in_ranking",
            field=models.BooleanField(default=True, help_text="Use this subject when computing class positions/rankings."),
        ),
    ]
