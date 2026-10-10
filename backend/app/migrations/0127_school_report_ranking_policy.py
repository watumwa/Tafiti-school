from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("app", "0126_staff_document_profile_fields")]

    operations = [
        migrations.AddField(
            model_name="schoolsetting",
            name="report_ranking_method",
            field=models.CharField(
                choices=[("AVERAGE", "Average score"), ("TOTAL", "Total score"), ("NONE", "Do not rank students")],
                default="AVERAGE",
                help_text="Controls how positions are calculated on performance reports and report cards.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="schoolsetting",
            name="report_tie_policy",
            field=models.CharField(
                choices=[("COMPETITION", "Competition ranking (1, 2, 2, 4)"), ("DENSE", "Dense ranking (1, 2, 2, 3)")],
                default="COMPETITION",
                help_text="Controls position numbering when students have equal ranking scores.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="schoolsetting",
            name="show_report_positions",
            field=models.BooleanField(
                default=True,
                help_text="Show class position on student reports when ranking is enabled.",
            ),
        ),
    ]
