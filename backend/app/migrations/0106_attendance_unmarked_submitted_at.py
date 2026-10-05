# Generated manually for safer attendance capture defaults.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0105_alter_staff_staff_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendancesession",
            name="submitted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="attendancerecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("unmarked", "Unmarked"),
                    ("present", "Present"),
                    ("late", "Late"),
                    ("absent", "Absent"),
                    ("excused", "Excused"),
                ],
                default="unmarked",
                max_length=20,
            ),
        ),
    ]
