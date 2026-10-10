from django.db import models
from django.conf import settings
from django.utils import timezone
from app.constants import AUDIENCE_CHOICES


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default="all")
    priority = models.CharField(
        max_length=10,
        choices=[("low", "Low"), ("normal", "Normal"), ("high", "High")],
        default="normal",
    )
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_announcements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_at", "-created_at"]

    def __str__(self):
        return self.title


class AnnouncementTarget(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="targets")
    staff = models.ForeignKey("app.Staff", on_delete=models.CASCADE, related_name="targeted_announcements")

    class Meta:
        unique_together = ("announcement", "staff")

    def __str__(self):
        return f"{self.announcement} -> {self.staff}"


class Event(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default="all")
    location = models.CharField(max_length=120, blank=True)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_datetime", "title"]

    def __str__(self):
        return self.title


class MessageThread(models.Model):
    subject = models.CharField(max_length=200, blank=True)
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="message_threads")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_threads",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.subject or f"Thread {self.pk}"


class Message(models.Model):
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_messages",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message {self.pk}"


class MessageThreadArchive(models.Model):
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name="archive_entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="archived_message_threads")
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("thread", "user")

    def __str__(self):
        return f"{self.thread} archived by {self.user}"


class CommunicationPreference(models.Model):
    student = models.OneToOneField("app.Student", on_delete=models.CASCADE, related_name="communication_preference")
    sms_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    whatsapp_enabled = models.BooleanField(default=False)
    guardian_email = models.EmailField(blank=True, default="")
    guardian_phone = models.CharField(max_length=50, blank=True, default="")
    whatsapp_number = models.CharField(max_length=50, blank=True, default="")
    consent_recorded_at = models.DateTimeField(null=True, blank=True)
    opted_out_at = models.DateTimeField(null=True, blank=True)

    @property
    def can_contact(self):
        return self.opted_out_at is None

    def __str__(self):
        return f"Communication preferences for {self.student}"


class OutboundNotification(models.Model):
    """One delivery attempt to a student's guardian through an external channel."""

    CHANNEL_SMS = "SMS"
    CHANNEL_EMAIL = "Email"
    CHANNEL_WHATSAPP = "WhatsApp"
    CHANNEL_CHOICES = [
        (CHANNEL_SMS, "SMS"),
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_WHATSAPP, "WhatsApp"),
    ]
    STATUS_QUEUED = "Queued"
    STATUS_SENT = "Sent"
    STATUS_FAILED = "Failed"
    STATUS_SKIPPED = "Skipped"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
        (STATUS_SKIPPED, "Skipped"),
    ]

    student = models.ForeignKey("app.Student", on_delete=models.CASCADE, related_name="outbound_messages")
    channel = models.CharField(max_length=12, choices=CHANNEL_CHOICES)
    recipient = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, blank=True, default="")
    body = models.TextField()
    template_key = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    provider_message_id = models.CharField(max_length=255, blank=True, default="")
    provider_response = models.TextField(blank=True, default="")
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.channel} to {self.recipient} ({self.status})"
