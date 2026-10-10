from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("app", "0125_completion_workflows")]

    operations = [
        migrations.AlterField(
            model_name="staffdocument",
            name="staff",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="app.staff"),
        ),
        migrations.AddField(
            model_name="staffdocument",
            name="uploaded_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AlterModelOptions(
            name="staffdocument",
            options={"ordering": ("-uploaded_at", "-id"), "verbose_name": "StaffDocument", "verbose_name_plural": "StaffDocuments"},
        ),
    ]
