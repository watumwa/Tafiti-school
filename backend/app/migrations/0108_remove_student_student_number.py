from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0107_classsubjectallocation_is_active"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="student",
            name="student_number",
        ),
    ]
