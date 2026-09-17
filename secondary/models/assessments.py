from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SecondaryCompetency(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        db_table = "app_secondarycompetency"

    def __str__(self):
        return f"{self.code} - {self.name}"


class SubjectCompetency(models.Model):
    subject = models.ForeignKey(
        "app.Subject",
        on_delete=models.CASCADE,
        related_name="secondary_competencies",
    )
    competency = models.ForeignKey(
        "secondary.SecondaryCompetency",
        on_delete=models.CASCADE,
        related_name="subject_links",
    )
    section = models.ForeignKey(
        "app.Section",
        on_delete=models.CASCADE,
        related_name="subject_competencies",
    )
    is_core = models.BooleanField(default=True)

    class Meta:
        unique_together = ("subject", "competency")
        db_table = "app_subjectcompetency"

    def __str__(self):
        return f"{self.subject} - {self.competency}"

    def clean(self):
        if self.subject_id and self.section_id and self.subject.section_id != self.section_id:
            raise ValidationError("Subject section must match competency link section.")


class ContinuousAssessmentTask(models.Model):
    class TaskType(models.TextChoices):
        PROJECT = "PROJECT", "Project"
        PRACTICAL = "PRACTICAL", "Practical"
        COURSEWORK = "COURSEWORK", "Coursework"
        PORTFOLIO = "PORTFOLIO", "Portfolio"
        PRESENTATION = "PRESENTATION", "Presentation"
        GROUP_WORK = "GROUP_WORK", "Group Work"
        ORAL = "ORAL", "Oral Task"
        FIELD_STUDY = "FIELD_STUDY", "Field Study"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_MODERATION = "PENDING_MODERATION", "Pending Moderation"
        MODERATED = "MODERATED", "Moderated"
        APPROVED = "APPROVED", "Approved"
        LOCKED = "LOCKED", "Locked"

    academic_class = models.ForeignKey(
        "app.AcademicClass",
        on_delete=models.CASCADE,
        related_name="ca_tasks",
    )
    term = models.ForeignKey(
        "app.Term",
        on_delete=models.CASCADE,
        related_name="ca_tasks",
    )
    subject = models.ForeignKey(
        "app.Subject",
        on_delete=models.CASCADE,
        related_name="ca_tasks",
    )
    subject_competency = models.ForeignKey(
        "secondary.SubjectCompetency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ca_tasks",
    )
    title = models.CharField(max_length=150)
    task_type = models.CharField(
        max_length=30,
        choices=TaskType.choices,
        default=TaskType.PROJECT,
    )
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("100.00"))
    assigned_date = models.DateField(default=timezone.now)
    evidence_required = models.BooleanField(default=False)
    uneb_eligible = models.BooleanField(default=True)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.DRAFT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ca_tasks_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ca_tasks_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-assigned_date", "-id"]
        unique_together = ("academic_class", "subject", "title", "assigned_date")
        db_table = "app_continuousassessmenttask"

    def __str__(self):
        return f"{self.academic_class} - {self.subject} - {self.title}"

    def clean(self):
        if self.weight < 0 or self.weight > 100:
            raise ValidationError("Task weight must be between 0 and 100.")

        if self.max_score <= 0:
            raise ValidationError("Maximum score must be greater than zero.")

        if self.academic_class_id and self.term_id and self.academic_class.term_id != self.term_id:
            raise ValidationError("Task term must match the academic class term.")

        if self.academic_class_id and self.subject_id:
            if self.academic_class.section_id != self.subject.section_id:
                raise ValidationError("Subject section must match the academic class section.")

        if self.subject_competency_id:
            if self.subject_competency.subject_id != self.subject_id:
                raise ValidationError("Selected subject competency does not belong to this subject.")


class ContinuousAssessmentRecord(models.Model):
    class ModerationStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING = "PENDING", "Pending Moderation"
        MODERATED = "MODERATED", "Moderated"
        APPROVED = "APPROVED", "Approved"
        LOCKED = "LOCKED", "Locked"
        REJECTED = "REJECTED", "Rejected"

    task = models.ForeignKey(
        "secondary.ContinuousAssessmentTask",
        on_delete=models.CASCADE,
        related_name="records",
    )
    student = models.ForeignKey(
        "app.Student",
        on_delete=models.CASCADE,
        related_name="ca_records",
    )
    raw_score = models.DecimalField(max_digits=6, decimal_places=2)
    moderated_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    teacher_comment = models.TextField(null=True, blank=True)
    evidence_reference = models.CharField(max_length=255, blank=True, default="")
    moderation_status = models.CharField(
        max_length=20,
        choices=ModerationStatus.choices,
        default=ModerationStatus.DRAFT,
    )
    is_locked = models.BooleanField(default=False)
    entered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ca_records_entered",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ca_records_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["task_id", "student_id"]
        unique_together = ("task", "student")
        db_table = "app_continuousassessmentrecord"

    def __str__(self):
        return f"{self.student} - {self.task} ({self.effective_score})"

    @property
    def effective_score(self):
        return self.moderated_score if self.moderated_score is not None else self.raw_score

    def clean(self):
        max_score = self.task.max_score if self.task_id else Decimal("0")
        if self.raw_score < 0 or self.raw_score > max_score:
            raise ValidationError("Raw score must be within task maximum score.")
        if self.moderated_score is not None and (self.moderated_score < 0 or self.moderated_score > max_score):
            raise ValidationError("Moderated score must be within task maximum score.")
        if self.is_locked and self.moderation_status == self.ModerationStatus.DRAFT:
            raise ValidationError("Locked records cannot stay in draft moderation status.")


class CAModeration(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        ADJUSTED = "ADJUSTED", "Adjusted"

    record = models.OneToOneField(
        "secondary.ContinuousAssessmentRecord",
        on_delete=models.CASCADE,
        related_name="moderation",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    moderated_score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    comments = models.TextField(null=True, blank=True)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ca_moderations_done",
    )
    moderated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-moderated_at"]
        db_table = "app_camoderation"

    def __str__(self):
        return f"Moderation {self.record_id} - {self.status}"

    def clean(self):
        if self.moderated_score is None:
            return
        max_score = self.record.task.max_score if self.record_id else Decimal("0")
        if self.moderated_score < 0 or self.moderated_score > max_score:
            raise ValidationError("Moderated score must be within task maximum score.")


class UNEBSubmissionBatch(models.Model):
    class Level(models.TextChoices):
        LOWER_SECONDARY = "LOWER_SECONDARY", "Lower Secondary (S1-S4)"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending Approval"
        APPROVED = "APPROVED", "Approved"
        SUBMITTED = "SUBMITTED", "Submitted to UNEB"
        LOCKED = "LOCKED", "Locked"
        REJECTED = "REJECTED", "Rejected"

    title = models.CharField(max_length=150, default="S4 UNEB CA Submission")
    section = models.ForeignKey(
        "app.Section",
        on_delete=models.CASCADE,
        related_name="uneb_ca_batches",
    )
    academic_year = models.ForeignKey(
        "app.AcademicYear",
        on_delete=models.CASCADE,
        related_name="uneb_ca_batches",
    )
    candidate_class = models.ForeignKey(
        "app.Class",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uneb_ca_batches",
    )
    level = models.CharField(max_length=30, choices=Level.choices, default=Level.LOWER_SECONDARY)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.DRAFT)
    submission_reference = models.CharField(max_length=100, blank=True, default="")
    notes = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uneb_ca_batches_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uneb_ca_batches_approved",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uneb_ca_batches_submitted",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        db_table = "app_unebsubmissionbatch"

    def __str__(self):
        return self.title


class UNEBSubmissionItem(models.Model):
    class ModerationStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING = "PENDING", "Pending Moderation"
        MODERATED = "MODERATED", "Moderated"
        APPROVED = "APPROVED", "Approved"
        LOCKED = "LOCKED", "Locked"
        REJECTED = "REJECTED", "Rejected"

    batch = models.ForeignKey(
        "secondary.UNEBSubmissionBatch",
        on_delete=models.CASCADE,
        related_name="items",
    )
    student = models.ForeignKey(
        "app.Student",
        on_delete=models.CASCADE,
        related_name="uneb_ca_items",
    )
    subject = models.ForeignKey(
        "app.Subject",
        on_delete=models.CASCADE,
        related_name="uneb_ca_items",
    )
    ca_mark = models.DecimalField(max_digits=5, decimal_places=2)
    final_ca_mark = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    source_task_count = models.PositiveIntegerField(default=0)
    evidence_count = models.PositiveIntegerField(default=0)
    moderation_status = models.CharField(
        max_length=20,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
    )
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student_id", "subject_id"]
        unique_together = ("batch", "student", "subject")
        db_table = "app_unebsubmissionitem"

    def __str__(self):
        return f"{self.batch} - {self.student} - {self.subject}"

    def clean(self):
        if self.ca_mark < 0 or self.ca_mark > 100:
            raise ValidationError("CA mark must be between 0 and 100.")
        if self.final_ca_mark is not None and (self.final_ca_mark < 0 or self.final_ca_mark > 100):
            raise ValidationError("Final CA mark must be between 0 and 100.")
