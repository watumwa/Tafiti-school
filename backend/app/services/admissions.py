from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from app.models import (
    AcademicClass, AcademicClassStream, AcademicYear, AdmissionApplication, AdmissionStatusHistory,
    ClassRegister, Student, Term,
)
from app.models.students import find_duplicate_student
from app.services.students import create_student_bill


class EnrollmentError(ValueError):
    pass


@transaction.atomic
def enroll_application(*, application_id, actor):
    application = AdmissionApplication.objects.select_for_update().select_related(
        "cycle__academic_year", "applying_class", "preferred_stream"
    ).get(pk=application_id)
    if application.status == AdmissionApplication.STATUS_ENROLLED and application.enrolled_student_id:
        return application.enrolled_student
    if application.status != AdmissionApplication.STATUS_ACCEPTED:
        raise EnrollmentError("Only an accepted application can be enrolled.")
    today = timezone.localdate()
    if not application.cycle.is_active or not application.cycle.opens_on <= today <= application.cycle.closes_on:
        raise EnrollmentError("The admission cycle is inactive or outside its opening dates.")
    if not application.preferred_stream_id:
        raise EnrollmentError("Select a preferred stream before enrollment.")
    duplicate = find_duplicate_student(
        student_name=application.student_name, birthdate=application.birthdate, contact=application.contact,
    )
    if duplicate:
        raise EnrollmentError(f"Possible duplicate student: {duplicate.reg_no}. Review the existing record.")
    current_terms = Term.objects.filter(academic_year=application.cycle.academic_year, is_current=True)
    if current_terms.count() != 1:
        if current_terms.exists():
            raise EnrollmentError("More than one current term exists for the admission year. Correct the term setup first.")
        raise EnrollmentError("No current term exists for the admission cycle's academic year.")
    term = current_terms.get()
    academic_class = AcademicClass.objects.filter(
        Class=application.applying_class, academic_year=application.cycle.academic_year, term=term,
    ).first()
    if not academic_class:
        raise EnrollmentError("The target academic class has not been configured for the current term.")
    class_stream = AcademicClassStream.objects.filter(
        academic_class=academic_class, stream=application.preferred_stream,
    ).first()
    if not class_stream:
        raise EnrollmentError("The preferred stream is not configured for the target academic class.")
    AcademicYear.objects.select_for_update().get(pk=application.cycle.academic_year_id)
    duplicate = find_duplicate_student(
        student_name=application.student_name,
        birthdate=application.birthdate,
        contact=application.contact,
    )
    if duplicate:
        raise EnrollmentError(f"Possible duplicate student: {duplicate.reg_no}. Review the existing record.")
    student = Student(
        student_name=application.student_name, gender=application.gender, birthdate=application.birthdate,
        nationality=application.nationality, religion=application.religion, address=application.address,
        guardian=application.guardian, relationship=application.relationship, contact=application.contact,
        academic_year=application.cycle.academic_year, current_class=application.applying_class,
        stream=application.preferred_stream, term=term,
    )
    try:
        student.full_clean(exclude=("reg_no",))
    except ValidationError as exc:
        raise EnrollmentError(f"The application cannot create a valid student record: {exc}") from exc
    student.save()
    ClassRegister.objects.get_or_create(academic_class_stream=class_stream, student=student)
    create_student_bill(student, academic_class)
    old_status = application.status
    application.status = AdmissionApplication.STATUS_ENROLLED
    application.enrolled_student = student
    application.save(update_fields=("status", "enrolled_student", "updated_at"))
    AdmissionStatusHistory.objects.create(
        application=application, from_status=old_status, to_status=application.status,
        notes="Student created through controlled enrollment.", changed_by=actor,
    )
    return student
