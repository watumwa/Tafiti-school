from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("app", "0129_uganda_student_identity_fee_plans_subject_flags")]

    operations = [
        migrations.CreateModel(
            name="CommunicationPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sms_enabled", models.BooleanField(default=True)),
                ("email_enabled", models.BooleanField(default=True)),
                ("whatsapp_enabled", models.BooleanField(default=False)),
                ("guardian_email", models.EmailField(blank=True, default="", max_length=254)),
                ("guardian_phone", models.CharField(blank=True, default="", max_length=50)),
                ("whatsapp_number", models.CharField(blank=True, default="", max_length=50)),
                ("consent_recorded_at", models.DateTimeField(blank=True, null=True)),
                ("opted_out_at", models.DateTimeField(blank=True, null=True)),
                ("student", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="communication_preference", to="app.student")),
            ],
        ),
        migrations.CreateModel(
            name="OutboundMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("SMS", "SMS"), ("Email", "Email"), ("WhatsApp", "WhatsApp")], max_length=12)),
                ("recipient", models.CharField(max_length=255)),
                ("subject", models.CharField(blank=True, default="", max_length=255)),
                ("body", models.TextField()),
                ("template_key", models.CharField(blank=True, default="", max_length=100)),
                ("status", models.CharField(choices=[("Queued", "Queued"), ("Sent", "Sent"), ("Failed", "Failed"), ("Skipped", "Skipped")], default="Queued", max_length=12)),
                ("provider_message_id", models.CharField(blank=True, default="", max_length=255)),
                ("provider_response", models.TextField(blank=True, default="")),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outbound_messages", to="app.student")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
