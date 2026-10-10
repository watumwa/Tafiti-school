from django.db import migrations, models

import app.validators


class Migration(migrations.Migration):
    dependencies = [("app", "0131_merge_role_permissions_uganda_features")]

    operations = [
        # Validation/help text are application-state changes only. Keeping this
        # migration database-neutral avoids touching the existing production
        # varchar column while ensuring future migration state matches models.py.
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="student",
                    name="lin_number",
                    field=models.CharField(
                        blank=True,
                        help_text=(
                            "Enter the official 14-character LIN issued by Uganda EMIS, "
                            "e.g. U13F0921A44760. Leave blank if not yet issued."
                        ),
                        max_length=40,
                        null=True,
                        unique=True,
                        validators=[app.validators.validate_uganda_lin],
                        verbose_name="Learner Identification Number (LIN)",
                    ),
                ),
            ],
        ),
    ]
