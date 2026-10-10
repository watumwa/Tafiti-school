from django.db import migrations, models


def add_missing_school_report_policy_columns(apps, schema_editor):
    """Add report-policy columns only when the physical table lacks them.

    Some production databases already contain these columns even though the
    migration recorder has not marked this migration as applied. Introspecting
    the live table lets Django reconcile the migration state without issuing
    duplicate-column DDL.
    """

    SchoolSetting = apps.get_model("app", "SchoolSetting")
    table_name = SchoolSetting._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(cursor, table_name)
    existing_columns = {column.name for column in description}

    fields = {
        "report_ranking_method": models.CharField(
            choices=[
                ("AVERAGE", "Average score"),
                ("TOTAL", "Total score"),
                ("NONE", "Do not rank students"),
            ],
            default="AVERAGE",
            help_text="Controls how positions are calculated on performance reports and report cards.",
            max_length=20,
        ),
        "report_tie_policy": models.CharField(
            choices=[
                ("COMPETITION", "Competition ranking (1, 2, 2, 4)"),
                ("DENSE", "Dense ranking (1, 2, 2, 3)"),
            ],
            default="COMPETITION",
            help_text="Controls position numbering when students have equal ranking scores.",
            max_length=20,
        ),
        "show_report_positions": models.BooleanField(
            default=True,
            help_text="Show class position on student reports when ranking is enabled.",
        ),
    }

    for name, field in fields.items():
        if name in existing_columns:
            continue
        field.set_attributes_from_name(name)
        field.model = SchoolSetting
        schema_editor.add_field(SchoolSetting, field)


class Migration(migrations.Migration):
    dependencies = [("app", "0126_staff_document_profile_fields")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_missing_school_report_policy_columns,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="schoolsetting",
                    name="report_ranking_method",
                    field=models.CharField(
                        choices=[
                            ("AVERAGE", "Average score"),
                            ("TOTAL", "Total score"),
                            ("NONE", "Do not rank students"),
                        ],
                        default="AVERAGE",
                        help_text="Controls how positions are calculated on performance reports and report cards.",
                        max_length=20,
                    ),
                ),
                migrations.AddField(
                    model_name="schoolsetting",
                    name="report_tie_policy",
                    field=models.CharField(
                        choices=[
                            ("COMPETITION", "Competition ranking (1, 2, 2, 4)"),
                            ("DENSE", "Dense ranking (1, 2, 2, 3)"),
                        ],
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
            ],
        ),
    ]
