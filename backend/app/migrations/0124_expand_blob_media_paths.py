from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0123_result_verification_toggle"),
    ]

    operations = [
        migrations.AlterField(
            model_name="student",
            name="photo",
            field=models.ImageField(
                blank=True,
                default="student_photos/default.jpg",
                max_length=500,
                null=True,
                upload_to="student_photos",
            ),
        ),
        migrations.AlterField(
            model_name="studentregistrationcsv",
            name="file_name",
            field=models.FileField(max_length=500, upload_to="media/csvs/"),
        ),
        migrations.AlterField(
            model_name="studentdocument",
            name="file",
            field=models.FileField(max_length=500, upload_to="student_documents/"),
        ),
        migrations.AlterField(
            model_name="staff",
            name="staff_photo",
            field=models.ImageField(max_length=500, upload_to="Staff/Profile_pics"),
        ),
        migrations.AlterField(
            model_name="staffdocument",
            name="file",
            field=models.FileField(max_length=500, upload_to="Staff/Documents"),
        ),
    ]
