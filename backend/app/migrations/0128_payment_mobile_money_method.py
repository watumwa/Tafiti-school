from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("app", "0127_school_report_ranking_policy")]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="payment_method",
            field=models.CharField(
                choices=[
                    ("Cash", "Cash"),
                    ("SchoolPay", "SchoolPay"),
                    ("Bank", "Bank"),
                    ("Mobile Money", "Mobile Money"),
                    ("Other", "Other"),
                ],
                max_length=50,
            ),
        ),
    ]
