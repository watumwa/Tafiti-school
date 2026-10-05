from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def use_legacy_mysql_engine(apps, schema_editor):
    """Match legacy MyISAM tables so MySQL can create cross-table fields."""
    if schema_editor.connection.vendor != "mysql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'app_student'"
        )
        row = cursor.fetchone()
        if row and (row[0] or "").upper() == "MYISAM":
            cursor.execute("SET SESSION default_storage_engine = MyISAM")


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0110_repair_cross_year_academic_classes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(use_legacy_mysql_engine, migrations.RunPython.noop),
        migrations.CreateModel(
            name="ReportCycleRemark",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope_key", models.CharField(max_length=255)),
                ("scope_label", models.CharField(max_length=255)),
                ("class_teacher_remark", models.CharField(blank=True, max_length=240)),
                ("head_teacher_remark", models.CharField(blank=True, max_length=240)),
                ("class_teacher_submitted_at", models.DateTimeField(blank=True, null=True)),
                ("head_teacher_approved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("academic_class", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="report_cycle_remarks", to="app.academicclass")),
                ("class_teacher_submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submitted_report_cycle_remarks", to=settings.AUTH_USER_MODEL)),
                ("head_teacher_approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_report_cycle_remarks", to=settings.AUTH_USER_MODEL)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="report_cycle_remarks", to="app.student")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_report_cycle_remarks", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["student__student_name", "student__reg_no"]},
        ),
        migrations.AddConstraint(
            model_name="reportcycleremark",
            constraint=models.UniqueConstraint(fields=("student", "academic_class", "scope_key"), name="uniq_report_cycle_remark_scope"),
        ),
    ]
