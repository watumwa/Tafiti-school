from django.db import migrations, models


def add_missing_staffaccount_security_columns(apps, schema_editor):
    """Add first-login security columns only when the physical table lacks them.

    Some production databases received these columns before the migration record
    was written.  Introspecting first lets Django reconcile migration history
    without attempting to create duplicate columns.
    """

    StaffAccount = apps.get_model("app", "StaffAccount")
    table_name = StaffAccount._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(cursor, table_name)
    existing_columns = {column.name for column in description}

    if "must_change_password" not in existing_columns:
        field = models.BooleanField(default=False)
        field.set_attributes_from_name("must_change_password")
        field.model = StaffAccount
        schema_editor.add_field(StaffAccount, field)

    if "temporary_password_expires_at" not in existing_columns:
        field = models.DateTimeField(blank=True, null=True)
        field.set_attributes_from_name("temporary_password_expires_at")
        field.model = StaffAccount
        schema_editor.add_field(StaffAccount, field)


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0120_schoolsetting_brand_colors"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_missing_staffaccount_security_columns,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
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
            ],
        ),
    ]
