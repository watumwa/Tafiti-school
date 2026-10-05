from django.db import models
from django.urls import reverse
from app.constants import GENDERS, NATIONALITIES, RELIGIONS, DOCUMENT_TYPES


def normalize_student_name(value):
    return " ".join(str(value or "").casefold().split())


def normalize_guardian_contact(value):
    return "".join(character for character in str(value or "") if character.isalnum()).casefold()


def find_duplicate_student(*, student_name, birthdate, contact, exclude_pk=None):
    """Return an existing student matching the stable registration identity fields."""
    normalized_name = normalize_student_name(student_name)
    normalized_contact = normalize_guardian_contact(contact)
    if not normalized_name or not birthdate or not normalized_contact:
        return None

    candidates = Student.objects.filter(birthdate=birthdate)
    if exclude_pk is not None:
        candidates = candidates.exclude(pk=exclude_pk)

    for candidate in candidates.only("id", "student_name", "birthdate", "contact", "reg_no"):
        if (
            normalize_student_name(candidate.student_name) == normalized_name
            and normalize_guardian_contact(candidate.contact) == normalized_contact
        ):
            return candidate
    return None

class Student(models.Model):
    reg_no = models.CharField(max_length=30, unique=True)
    student_name = models.CharField(max_length=50)
    gender = models.CharField(max_length=2, choices=GENDERS)
    birthdate = models.DateField(auto_now=False)
    nationality = models.CharField(max_length=30, choices=NATIONALITIES)
    religion = models.CharField(max_length=30, choices=RELIGIONS)
    address = models.CharField(max_length=150)
    guardian = models.CharField(max_length=50, verbose_name="Guardian Name")
    relationship = models.CharField(max_length=50)
    contact = models.CharField(max_length=50, verbose_name="Guardian Contact")
    academic_year = models.ForeignKey("app.AcademicYear", verbose_name=("Entry Year"), on_delete=models.CASCADE)
    current_class = models.ForeignKey("app.Class", verbose_name="Current Class", on_delete=models.CASCADE)
    stream = models.ForeignKey("app.Stream", on_delete=models.CASCADE)
    term = models.ForeignKey("app.Term", on_delete=models.CASCADE)
    photo = models.ImageField(upload_to="student_photos", null=True, blank=True, default="student_photos/default.jpg")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = ("student")
        verbose_name_plural = ("students")
        constraints = [
            models.UniqueConstraint(
                fields=("student_name", "birthdate", "contact"),
                name="unique_student_identity",
            )
        ]

    def __str__(self):
        return self.student_name

    @property
    def display_student_id(self):
        return self.reg_no or str(self.pk)

    def get_absolute_url(self):
        return reverse("student_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        needs_generation = is_new or not self.reg_no

        if needs_generation and not self.reg_no:
            self.reg_no = self._build_unique_reg_no()

        super().save(*args, **kwargs)

    def _build_unique_reg_no(self) -> str:
        prefix = "ST"

        existing = Student.objects.filter(reg_no__startswith=prefix).values_list('reg_no', flat=True)
        max_seq = 0
        for rn in existing:
            suffix = str(rn or "")[len(prefix):]
            if not suffix.isdigit():
                continue
            max_seq = max(max_seq, int(suffix))

        next_seq = max_seq + 1
        candidate = f"{prefix}{next_seq:04d}"
        while Student.objects.filter(reg_no=candidate).exists():
            next_seq += 1
            candidate = f"{prefix}{next_seq:04d}"
        return candidate

class StudentRegistrationCSV(models.Model):
    file_name = models.FileField(upload_to='media/csvs/')
    uploaded = models.DateTimeField(auto_now_add=True)
    activated = models.BooleanField(default=False)

    def __str__(self):
        return f"File ID: {self.id}"
    
class StudentDocument(models.Model):
    student = models.ForeignKey("app.Student", on_delete=models.CASCADE, related_name='documents')
    bill = models.ForeignKey("app.StudentBill", on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to='student_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = ("Student Document")
        verbose_name_plural = ("Student Documents")
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.document_type} - {self.student.student_name}"

    def get_absolute_url(self):
        return reverse("student_document_detail", kwargs={"pk": self.pk})


class ClassRegister(models.Model):

    academic_class_stream = models.ForeignKey("app.AcademicClassStream", on_delete=models.CASCADE)
    student = models.ForeignKey("app.Student", on_delete=models.CASCADE)
    payment_status = models.CharField(max_length=10, default=0)

    class Meta:
        verbose_name = ("ClassRegister")
        verbose_name_plural = ("ClassRegisters")
        unique_together = ("academic_class_stream", "student")

    def __str__(self):
       return f"{self.academic_class_stream} - {self.student}"

    def get_absolute_url(self):
        return reverse("ClassRegister_detail", kwargs={"pk": self.pk})
