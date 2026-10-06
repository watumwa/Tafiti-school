from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0120_schoolsetting_brand_colors"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentFeeAdjustment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("adjustment_type", models.CharField(choices=[("Bursary", "Bursary"), ("Scholarship", "Scholarship"), ("Staff Child Discount", "Staff Child Discount"), ("Sibling Discount", "Sibling Discount"), ("Waiver", "Waiver"), ("Sponsor", "Sponsor"), ("Other", "Other")], default="Bursary", max_length=40)),
                ("calculation_type", models.CharField(choices=[("Fixed", "Fixed amount"), ("Percentage", "Percentage")], default="Fixed", max_length=12)),
                ("value", models.DecimalField(decimal_places=2, max_digits=10)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("reason", models.TextField(blank=True, default="")),
                ("status", models.CharField(choices=[("Approved", "Approved"), ("Cancelled", "Cancelled")], default="Approved", max_length=12)),
                ("created_by", models.CharField(blank=True, default="", max_length=150)),
                ("approved_by", models.CharField(blank=True, default="", max_length=150)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("bill", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fee_adjustments", to="app.studentbill")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
