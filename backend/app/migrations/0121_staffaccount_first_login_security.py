from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0120_schoolsetting_brand_colors"),
    ]

    operations = [
        migrations.AddField(
            model_name="staffaccount",
            name="must_change_password",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="staffaccount",
            name="temporary_password_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
