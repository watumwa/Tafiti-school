from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0119_merge_duplicate_students_and_guard_identity"),
    ]

    operations = [
        migrations.AddField(
            model_name="schoolsetting",
            name="primary_color",
            field=models.CharField(default="#087F5B", max_length=7),
        ),
        migrations.AddField(
            model_name="schoolsetting",
            name="secondary_color",
            field=models.CharField(default="#07543F", max_length=7),
        ),
        migrations.AddField(
            model_name="schoolsetting",
            name="accent_color",
            field=models.CharField(default="#D79B35", max_length=7),
        ),
    ]