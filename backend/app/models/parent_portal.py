"""Parent Portal authentication, authorization and audit models."""
from django.conf import settings
from django.db import models
from django.utils import timezone


class ParentAccess(models.Model):
    """Authorises one login to read one existing student's information."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="parent_accesses")
    student = models.ForeignKey("app.Student", on_delete=models.CASCADE, related_name="parent_accesses")
    can_view_academics = models.BooleanField(default=True)
    can_view_finance = models.BooleanField(default=True)
    can_view_attendance = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=True)
    temporary_password_expires_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="verified_parent_accesses",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "student"), name="unique_parent_user_student_access"),
        ]
        indexes = [
            models.Index(fields=("user", "is_active"), name="parent_access_user_active_idx"),
            models.Index(fields=("student", "is_active"), name="parent_student_active_idx"),
        ]

    @property
    def temporary_password_expired(self):
        return bool(self.temporary_password_expires_at and self.temporary_password_expires_at <= timezone.now())

    def __str__(self):
        return f"{self.user.username} -> {self.student}"


class ParentPortalAudit(models.Model):
    ACTION_LOGIN = "login"
    ACTION_LOGIN_FAILED = "login_failed"
    ACTION_ACTIVATED = "activated"
    ACTION_PASSWORD_CHANGED = "password_changed"
    ACTION_VIEWED = "viewed"
    ACTION_ACCESS_CHANGED = "access_changed"
    ACTION_DEACTIVATED = "deactivated"
    ACTION_PASSWORD_RESET = "password_reset"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    student = models.ForeignKey("app.Student", null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=40)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("action", "created_at"), name="parent_audit_action_time_idx")]


class ParentNotification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="parent_notifications")
    student = models.ForeignKey("app.Student", null=True, blank=True, on_delete=models.CASCADE, related_name="parent_notifications")
    kind = models.CharField(max_length=30)
    title = models.CharField(max_length=180)
    message = models.CharField(max_length=500, blank=True)
    destination = models.CharField(max_length=255, blank=True)
    source_key = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("user", "source_key"), name="unique_parent_notification_source")]
        indexes = [models.Index(fields=("user", "read_at", "created_at"), name="parent_notice_read_idx")]


class ParentConversation(models.Model):
    parent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="parent_conversations")
    student = models.ForeignKey("app.Student", on_delete=models.CASCADE, related_name="parent_conversations")
    staff = models.ForeignKey("app.Staff", on_delete=models.PROTECT, related_name="parent_conversations")
    thread = models.OneToOneField("app.MessageThread", on_delete=models.CASCADE, related_name="parent_conversation")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("parent", "student", "staff"), name="unique_parent_student_staff_conversation")
        ]
        ordering = ("-thread__updated_at",)
