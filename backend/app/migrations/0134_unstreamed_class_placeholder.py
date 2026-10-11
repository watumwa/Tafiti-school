from django.db import migrations, models
import django.db.models.deletion


NO_STREAM_VALUE = "-"


def ensure_no_stream_sentinel(apps, schema_editor):
    Stream = apps.get_model("app", "Stream")
    Stream.objects.get_or_create(stream=NO_STREAM_VALUE)


class Migration(migrations.Migration):
    dependencies = [("app", "0133_classbill_residency_uniqueness")]

    operations = [
        migrations.AlterField(
            model_name="academicclassstream",
            name="class_teacher",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="app.staff",
            ),
        ),
        migrations.RunPython(ensure_no_stream_sentinel, migrations.RunPython.noop),
    ]
