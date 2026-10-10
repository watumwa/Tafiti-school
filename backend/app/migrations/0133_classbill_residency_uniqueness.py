from django.db import migrations


OLD_FIELDS = ("academic_class", "bill_item")
NEW_FIELDS = ("academic_class", "bill_item", "applies_to")


def _has_unique_constraint(connection, table_name, columns):
    expected = set(columns)
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table_name)
    return any(
        details.get("unique") and set(details.get("columns") or []) == expected
        for details in constraints.values()
    )


def forwards(apps, schema_editor):
    ClassBill = apps.get_model("app", "ClassBill")
    table_name = ClassBill._meta.db_table
    connection = schema_editor.connection

    old_columns = ("academic_class_id", "bill_item_id")
    new_columns = ("academic_class_id", "bill_item_id", "applies_to")

    if _has_unique_constraint(connection, table_name, new_columns):
        return

    old_unique = {OLD_FIELDS} if _has_unique_constraint(connection, table_name, old_columns) else set()
    schema_editor.alter_unique_together(ClassBill, old_unique, {NEW_FIELDS})


def backwards(apps, schema_editor):
    ClassBill = apps.get_model("app", "ClassBill")
    table_name = ClassBill._meta.db_table
    connection = schema_editor.connection

    old_columns = ("academic_class_id", "bill_item_id")
    new_columns = ("academic_class_id", "bill_item_id", "applies_to")

    if _has_unique_constraint(connection, table_name, old_columns):
        return

    new_unique = {NEW_FIELDS} if _has_unique_constraint(connection, table_name, new_columns) else set()
    schema_editor.alter_unique_together(ClassBill, new_unique, {OLD_FIELDS})


class Migration(migrations.Migration):
    dependencies = [("app", "0132_student_lin_format_validation")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(forwards, backwards)],
            state_operations=[
                migrations.AlterUniqueTogether(
                    name="classbill",
                    unique_together={NEW_FIELDS},
                ),
            ],
        ),
    ]
