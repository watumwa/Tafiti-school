from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP

from django.db.models import Count, Q
from django.utils import timezone

from app.models.attendance import AttendancePolicy, AttendanceRecord, AttendanceStatus
from app.models.classes import AcademicClass, AcademicClassStream, Class, ClassSubjectAllocation
from app.models.results import AssessmentType, ReportRemark, Result
from app.models.school_settings import SchoolSetting, Signature
from app.models.students import ClassRegister, Student
from app.models.subjects import Subject
from secondary.models import (
    ALevelAssessmentRecord,
    ALevelCompetencyScale,
    ALevelComponentWeight,
    ALevelSubjectResult,
    ALevelSubjectModule,
    ContinuousAssessmentRecord,
    SecondaryCompetency,
    SecondaryComputationPolicy,
    SecondaryOverallResult,
    SecondarySubjectResult,
    StudentSubjectEnrollment,
    UNEBSubmissionItem,
)


LOWER_POLICY_LEVEL = SecondaryComputationPolicy.Level.LOWER_SECONDARY
UPPER_POLICY_LEVEL = SecondaryComputationPolicy.Level.UPPER_SECONDARY
SECONDARY_EXAM_TYPE_NAME = "END OF TERM"
SECONDARY_EXAM_TYPE_FILTER = (
    Q(name__iexact="END OF TERM")
    | Q(name__iexact="END OF TERM INTERNAL")
    | Q(name__iexact="END OF TERM EXTERNAL")
    | Q(name__icontains="END OF TERM")
    | Q(name__icontains="EOT")
    | Q(name__icontains="EXAM")
)
EOT_NAME_FILTER = (
    Q(assessment__assessment_type__name__iexact="END OF TERM INTERNAL")
    | Q(assessment__assessment_type__name__iexact="END OF TERM EXTERNAL")
    | Q(assessment__assessment_type__name__iexact="END OF TERM")
    | Q(assessment__assessment_type__name__icontains="END OF TERM")
    | Q(assessment__assessment_type__name__icontains="EOT")
)
FALLBACK_EXAM_FILTER = Q(assessment__assessment_type__name__icontains="EXAM")
PROJECT_TASK_TYPES = {
    "PROJECT",
    "PRACTICAL",
    "FIELD_STUDY",
    "PORTFOLIO",
    "PRESENTATION",
    "GROUP_WORK",
}
LOWER_SECONDARY_SUBJECT_RULES = {
    "S1": {
        "label": "Senior 1-2",
        "required_core": 11,
        "min_electives": 1,
        "max_electives": 1,
    },
    "S2": {
        "label": "Senior 1-2",
        "required_core": 11,
        "min_electives": 1,
        "max_electives": 1,
    },
    "O1": {
        "label": "Senior 1-2",
        "required_core": 11,
        "min_electives": 1,
        "max_electives": 1,
    },
    "O2": {
        "label": "Senior 1-2",
        "required_core": 11,
        "min_electives": 1,
        "max_electives": 1,
    },
    "S3": {
        "label": "Senior 3-4",
        "required_core": 7,
        "min_electives": 0,
        "max_electives": 2,
    },
    "S4": {
        "label": "Senior 3-4",
        "required_core": 7,
        "min_electives": 0,
        "max_electives": 2,
    },
    "O3": {
        "label": "Senior 3-4",
        "required_core": 7,
        "min_electives": 0,
        "max_electives": 2,
    },
    "O4": {
        "label": "Senior 3-4",
        "required_core": 7,
        "min_electives": 0,
        "max_electives": 2,
    },
}


def _to_decimal(value, default="0.00"):
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _quantize(value, places="0.01"):
    if value is None:
        return None
    return _to_decimal(value).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _round_for_policy(value, policy):
    if value is None:
        return None
    value = _to_decimal(value)
    if not policy:
        return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if policy.rounding_mode == SecondaryComputationPolicy.RoundingMode.WHOLE_NUMBER:
        return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if policy.rounding_mode == SecondaryComputationPolicy.RoundingMode.WHOLE_NUMBER_DOWN:
        return value.quantize(Decimal("1"), rounding=ROUND_DOWN)
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _derive_uneb_item_moderation_status(record_statuses):
    if not record_statuses:
        return UNEBSubmissionItem.ModerationStatus.PENDING

    if ContinuousAssessmentRecord.ModerationStatus.REJECTED in record_statuses:
        return UNEBSubmissionItem.ModerationStatus.REJECTED

    if record_statuses.issubset(
        {
            ContinuousAssessmentRecord.ModerationStatus.APPROVED,
            ContinuousAssessmentRecord.ModerationStatus.LOCKED,
        }
    ):
        return UNEBSubmissionItem.ModerationStatus.APPROVED

    if record_statuses.intersection(
        {
            ContinuousAssessmentRecord.ModerationStatus.MODERATED,
            ContinuousAssessmentRecord.ModerationStatus.APPROVED,
            ContinuousAssessmentRecord.ModerationStatus.LOCKED,
        }
    ):
        return UNEBSubmissionItem.ModerationStatus.MODERATED

    if ContinuousAssessmentRecord.ModerationStatus.PENDING in record_statuses:
        return UNEBSubmissionItem.ModerationStatus.PENDING

    if ContinuousAssessmentRecord.ModerationStatus.DRAFT in record_statuses:
        return UNEBSubmissionItem.ModerationStatus.DRAFT

    return UNEBSubmissionItem.ModerationStatus.PENDING


def get_policy_for_date(section, target_date=None, level=LOWER_POLICY_LEVEL):
    target_date = target_date or timezone.localdate()
    queryset = (
        SecondaryComputationPolicy.objects.filter(
            section=section,
            level=level,
            is_active=True,
            effective_from__lte=target_date,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=target_date))
        .order_by("-effective_from", "-id")
    )
    policy = queryset.first()
    if policy:
        return policy
    return (
        SecondaryComputationPolicy.objects.filter(section=section, level=level)
        .order_by("-effective_from", "-id")
        .first()
    )


def get_secondary_exam_assessment_types():
    AssessmentType.objects.get_or_create(
        name=SECONDARY_EXAM_TYPE_NAME,
        defaults={"weight": Decimal("80.00")},
    )
    return AssessmentType.objects.filter(SECONDARY_EXAM_TYPE_FILTER).order_by("name")


def _level_tone(grade, descriptor, score=None):
    grade_text = (grade or "").strip().lower()
    desc_text = (descriptor or "").strip().lower()
    text = f"{grade_text} {desc_text}"
    if any(token in text for token in ("begin", "below", "emerg", "novice", "f", "e")):
        return "beginning"
    if any(token in text for token in ("develop", "fair", "improv", "d")):
        return "developing"
    if any(token in text for token in ("profic", "compet", "good", "b", "c")):
        return "proficient"
    if any(token in text for token in ("adv", "excellent", "master", "a")):
        return "advanced"

    numeric_score = _to_decimal(score, default="0")
    if numeric_score < 40:
        return "beginning"
    if numeric_score < 60:
        return "developing"
    if numeric_score < 80:
        return "proficient"
    return "advanced"


def get_level_for_score(score, policy=None):
    if score is None:
        return {
            "short_label": "-",
            "label": "No evidence",
            "descriptor": "No evidence",
            "grade": "",
            "tone": "default",
        }

    score = _to_decimal(score)
    band = None
    if policy:
        band = (
            policy.grade_bands.filter(min_score__lte=score, max_score__gte=score)
            .order_by("display_order", "-min_score")
            .first()
        )

    if band:
        grade = band.grade
        descriptor = band.descriptor
    else:
        if score < 40:
            grade, descriptor = "B", "Beginning"
        elif score < 60:
            grade, descriptor = "D", "Developing"
        elif score < 80:
            grade, descriptor = "P", "Proficient"
        else:
            grade, descriptor = "A", "Advanced"

    return {
        "short_label": grade,
        "label": descriptor,
        "descriptor": descriptor,
        "grade": grade,
        "tone": _level_tone(grade, descriptor, score),
    }


def get_students_for_academic_class(academic_class):
    student_ids = (
        ClassRegister.objects.filter(academic_class_stream__academic_class=academic_class)
        .values_list("student_id", flat=True)
        .distinct()
    )
    return Student.objects.filter(id__in=student_ids).order_by("student_name")


def get_lower_secondary_subject_rule(academic_class):
    if academic_class is None or getattr(academic_class, "Class", None) is None:
        return None
    code = (academic_class.Class.code or "").upper()
    return LOWER_SECONDARY_SUBJECT_RULES.get(code)


def get_student_subject_load(academic_class, student, *, extra_subject=None, extra_subject_is_active=True):
    enrollments = get_subject_enrollments_for_class(academic_class).filter(student=student)
    core_subject_ids = set(
        get_allocated_subjects_for_student(academic_class, student, core_only=True).values_list("id", flat=True)
    )
    core_subject_ids.update(
        enrollments.filter(Q(is_compulsory=True) | Q(subject__type__iexact="Core")).values_list(
            "subject_id",
            flat=True,
        )
    )
    elective_subject_ids = set(
        enrollments.filter(subject__type__iexact="Elective").values_list("subject_id", flat=True)
    )

    if extra_subject is not None and extra_subject_is_active:
        if (extra_subject.type or "").strip().lower() == "core":
            core_subject_ids.add(extra_subject.id)
        else:
            elective_subject_ids.add(extra_subject.id)

    return {
        "core_subject_ids": sorted(core_subject_ids),
        "elective_subject_ids": sorted(elective_subject_ids),
        "core_count": len(core_subject_ids),
        "elective_count": len(elective_subject_ids),
    }


def evaluate_subject_load(academic_class, student, *, extra_subject=None, extra_subject_is_active=True):
    rule = get_lower_secondary_subject_rule(academic_class)
    load = get_student_subject_load(
        academic_class,
        student,
        extra_subject=extra_subject,
        extra_subject_is_active=extra_subject_is_active,
    )
    blocking_issues = []
    warnings = []

    if rule:
        if load["core_count"] > rule["required_core"]:
            blocking_issues.append(
                f"Core subject load exceeds the Uganda CBC requirement of {rule['required_core']}."
            )
        elif load["core_count"] < rule["required_core"]:
            warnings.append(
                f"Core subject load is below the Uganda CBC requirement of {rule['required_core']}."
            )

        if load["elective_count"] > rule["max_electives"]:
            blocking_issues.append(
                f"Elective subject load exceeds the Uganda CBC maximum of {rule['max_electives']}."
            )
        elif load["elective_count"] < rule["min_electives"]:
            warnings.append(
                f"Elective subject load is below the Uganda CBC minimum of {rule['min_electives']}."
            )

    return {
        "rule": rule,
        "core_count": load["core_count"],
        "elective_count": load["elective_count"],
        "blocking_issues": blocking_issues,
        "warnings": warnings,
        "is_compliant": not blocking_issues and not warnings,
    }


def build_curriculum_summary_for_class(academic_class):
    rule = get_lower_secondary_subject_rule(academic_class)
    students = list(get_students_for_academic_class(academic_class))
    rows = []
    non_compliant_count = 0
    for student in students:
        status = evaluate_subject_load(academic_class, student)
        issues = [*status["blocking_issues"], *status["warnings"]]
        if issues:
            non_compliant_count += 1
        rows.append(
            {
                "student": student,
                "core_count": status["core_count"],
                "elective_count": status["elective_count"],
                "issues": issues,
                "is_compliant": not issues,
            }
        )

    offered_core_count = (
        Subject.objects.filter(
            subjects__academic_class_stream__academic_class=academic_class,
            type__iexact="Core",
        )
        .distinct()
        .count()
    )
    offered_elective_count = (
        Subject.objects.filter(
            subjects__academic_class_stream__academic_class=academic_class,
            type__iexact="Elective",
        )
        .distinct()
        .count()
    )
    allocation_issues = []
    if rule:
        if offered_core_count != rule["required_core"]:
            allocation_issues.append(
                f"Class allocations expose {offered_core_count} core subject(s); Uganda CBC expects {rule['required_core']}."
            )
        if rule["min_electives"] > 0 and offered_elective_count < rule["min_electives"]:
            allocation_issues.append(
                f"Class allocations expose {offered_elective_count} elective subject(s); at least {rule['min_electives']} is required."
            )

    return {
        "rule": rule,
        "rows": rows,
        "non_compliant_count": non_compliant_count,
        "student_count": len(students),
        "offered_core_count": offered_core_count,
        "offered_elective_count": offered_elective_count,
        "allocation_issues": allocation_issues,
    }


def get_subject_enrollments_for_class(academic_class):
    return StudentSubjectEnrollment.objects.filter(
        academic_class=academic_class,
        is_active=True,
    ).select_related("student", "subject")


def get_allocated_subjects_for_student(academic_class, student, *, core_only=False):
    queryset = Subject.objects.filter(
        subjects__academic_class_stream__academic_class=academic_class,
        subjects__academic_class_stream__classregister__student=student,
    )
    if core_only:
        queryset = queryset.filter(type__iexact="Core")
    return queryset.distinct().order_by("name")


def get_students_for_subject(academic_class, subject):
    if (subject.type or "").strip().lower() == "core":
        allocated_student_ids = (
            ClassRegister.objects.filter(
                academic_class_stream__academic_class=academic_class,
                academic_class_stream__subjects__subject=subject,
            )
            .values_list("student_id", flat=True)
            .distinct()
        )
        queryset = Student.objects.filter(id__in=allocated_student_ids).order_by("student_name")
        if queryset.exists():
            return queryset
        return get_students_for_academic_class(academic_class)

    enrollment_qs = get_subject_enrollments_for_class(academic_class).filter(subject=subject)
    if enrollment_qs.exists():
        return Student.objects.filter(
            id__in=enrollment_qs.values_list("student_id", flat=True)
        ).order_by("student_name")

    inferred_student_ids = (
        ContinuousAssessmentRecord.objects.filter(
            task__academic_class=academic_class,
            task__subject=subject,
        ).values_list("student_id", flat=True)
    )
    inferred_student_ids = set(inferred_student_ids).union(
        Result.objects.filter(
            assessment__academic_class=academic_class,
            assessment__subject=subject,
        ).values_list("student_id", flat=True)
    )
    return Student.objects.filter(id__in=inferred_student_ids).order_by("student_name")


def _student_subjects_for_class(student, academic_class):
    enrollment_subject_ids = set(
        get_subject_enrollments_for_class(academic_class)
        .filter(student=student)
        .values_list("subject_id", flat=True)
        .distinct()
    )
    allocated_core_subject_ids = set(
        get_allocated_subjects_for_student(academic_class, student, core_only=True).values_list("id", flat=True)
    )

    task_subject_ids = ContinuousAssessmentRecord.objects.filter(
        student=student,
        task__academic_class=academic_class,
    ).values_list("task__subject_id", flat=True)
    exam_subject_ids = Result.objects.filter(
        student=student,
        assessment__academic_class=academic_class,
    ).values_list("assessment__subject_id", flat=True)
    subject_ids = sorted({*enrollment_subject_ids, *allocated_core_subject_ids, *task_subject_ids, *exam_subject_ids})
    return Subject.objects.filter(id__in=subject_ids).order_by("name")


def sync_subject_enrollments_from_allocations(academic_class, *, include_electives=False):
    allocations = ClassSubjectAllocation.objects.filter(
        academic_class_stream__academic_class=academic_class
    ).select_related("subject")
    if not include_electives:
        allocations = allocations.filter(subject__type__iexact="Core")
    rule = get_lower_secondary_subject_rule(academic_class)
    max_electives = rule["max_electives"] if rule else None

    allocations_by_stream = defaultdict(list)
    for allocation in allocations:
        allocations_by_stream[allocation.academic_class_stream_id].append(allocation.subject)

    created = 0
    reactivated = 0
    unchanged = 0
    skipped = 0
    for register in ClassRegister.objects.filter(
        academic_class_stream__academic_class=academic_class
    ).select_related("student", "academic_class_stream"):
        stream_subjects = allocations_by_stream.get(register.academic_class_stream_id, [])
        subjects_to_sync = [subject for subject in stream_subjects if (subject.type or "").strip().lower() == "core"]
        elective_subjects = [
            subject for subject in stream_subjects if (subject.type or "").strip().lower() != "core"
        ]
        if include_electives and elective_subjects:
            if max_electives is not None:
                current_load = get_student_subject_load(academic_class, register.student)
                remaining_elective_slots = max(max_electives - current_load["elective_count"], 0)
                if len(elective_subjects) > remaining_elective_slots:
                    skipped += len(elective_subjects)
                else:
                    subjects_to_sync.extend(elective_subjects)
            else:
                subjects_to_sync.extend(elective_subjects)

        for subject in subjects_to_sync:
            enrollment, created_flag = StudentSubjectEnrollment.objects.get_or_create(
                academic_class=academic_class,
                student=register.student,
                subject=subject,
                defaults={
                    "is_active": True,
                    "is_compulsory": (subject.type or "").strip().lower() == "core",
                },
            )
            if created_flag:
                created += 1
                continue

            changed = False
            compulsory_flag = (subject.type or "").strip().lower() == "core"
            if not enrollment.is_active:
                enrollment.is_active = True
                changed = True
            if enrollment.is_compulsory != compulsory_flag:
                enrollment.is_compulsory = compulsory_flag
                changed = True
            if changed:
                enrollment.save(update_fields=["is_active", "is_compulsory", "updated_at"])
                reactivated += 1
            else:
                unchanged += 1

    return {
        "created": created,
        "reactivated": reactivated,
        "unchanged": unchanged,
        "skipped": skipped,
    }


def get_ca_records(student, academic_class, subject=None, include_rejected=False):
    queryset = (
        ContinuousAssessmentRecord.objects.filter(student=student, task__academic_class=academic_class)
        .select_related(
            "task",
            "task__subject",
            "task__subject_competency__competency",
        )
        .order_by("task__assigned_date", "task__title", "id")
    )
    if subject is not None:
        queryset = queryset.filter(task__subject=subject)
    if not include_rejected:
        queryset = queryset.exclude(moderation_status=ContinuousAssessmentRecord.ModerationStatus.REJECTED)
    return list(queryset)


def calculate_ca_average(records):
    if not records:
        return None

    weighted_total = Decimal("0.00")
    total_weight = Decimal("0.00")
    normalized_scores = []
    for record in records:
        max_score = _to_decimal(record.task.max_score)
        if max_score <= 0:
            continue
        normalized = (_to_decimal(record.effective_score) / max_score) * Decimal("100")
        normalized_scores.append(normalized)
        weight = _to_decimal(record.task.weight)
        if weight > 0:
            weighted_total += normalized * weight
            total_weight += weight

    if total_weight > 0:
        return weighted_total / total_weight
    if normalized_scores:
        return sum(normalized_scores) / Decimal(len(normalized_scores))
    return None


def get_exam_score(student, academic_class, subject):
    base_queryset = Result.objects.filter(
        student=student,
        assessment__academic_class=academic_class,
        assessment__subject=subject,
    ).select_related("assessment", "assessment__assessment_type")
    preferred = base_queryset.filter(EOT_NAME_FILTER)
    if preferred.exists():
        scores = []
        for row in preferred:
            out_of = _to_decimal(getattr(row.assessment, "out_of", 100), default="100")
            if out_of <= 0:
                continue
            scores.append((_to_decimal(row.score) / out_of) * Decimal("100"))
    else:
        fallback = base_queryset.filter(FALLBACK_EXAM_FILTER)
        scores = []
        if fallback.exists():
            for row in fallback:
                out_of = _to_decimal(getattr(row.assessment, "out_of", 100), default="100")
                if out_of <= 0:
                    continue
                scores.append((_to_decimal(row.score) / out_of) * Decimal("100"))
    if not scores:
        return None
    return sum(scores) / Decimal(len(scores))


def compute_subject_result(student, academic_class, subject, policy=None, exam_score=None, persist=False):
    policy = policy or get_policy_for_date(
        academic_class.section,
        target_date=getattr(academic_class.term, "end_date", None),
    )
    records = get_ca_records(student, academic_class, subject=subject)
    ca_score = calculate_ca_average(records)
    resolved_exam_score = _to_decimal(exam_score) if exam_score is not None else get_exam_score(
        student,
        academic_class,
        subject,
    )

    if ca_score is not None and resolved_exam_score is not None:
        final_score = ((_to_decimal(policy.ca_weight or 20) * ca_score) + (_to_decimal(policy.exam_weight or 80) * resolved_exam_score)) / Decimal(
            "100"
        ) if policy else ((Decimal("20") * ca_score) + (Decimal("80") * resolved_exam_score)) / Decimal("100")
    elif ca_score is not None:
        final_score = ca_score
    else:
        final_score = resolved_exam_score

    display_ca_score = _round_for_policy(ca_score, policy) if ca_score is not None else None
    display_exam_score = _round_for_policy(resolved_exam_score, policy) if resolved_exam_score is not None else None
    display_final_score = _round_for_policy(final_score, policy) if final_score is not None else None
    level = get_level_for_score(display_final_score if display_final_score is not None else final_score, policy=policy)

    details = []
    competency_scores = defaultdict(list)
    teacher_comments = []
    for record in records:
        max_score = _to_decimal(record.task.max_score)
        normalized = None
        if max_score > 0:
            normalized = (_to_decimal(record.effective_score) / max_score) * Decimal("100")
        normalized_display = _round_for_policy(normalized, policy) if normalized is not None else None
        competency = getattr(getattr(record.task, "subject_competency", None), "competency", None)
        if competency and normalized is not None:
            competency_scores[competency.id].append(normalized)
        if record.teacher_comment:
            teacher_comments.append(record.teacher_comment.strip())
        details.append(
            {
                "task_title": record.task.title,
                "task_type": record.task.get_task_type_display(),
                "score": _quantize(record.effective_score),
                "max_score": _quantize(record.task.max_score),
                "normalized_score": normalized_display,
                "competency_id": competency.id if competency else None,
                "competency_name": competency.name if competency else "",
                "teacher_comment": record.teacher_comment,
                "evidence_reference": record.evidence_reference,
                "task_type_code": record.task.task_type,
            }
        )

    teacher_comment = teacher_comments[-1] if teacher_comments else ""

    result_payload = {
        "subject": subject,
        "subject_name": subject.name,
        "ca_score": display_ca_score,
        "eot_score": display_exam_score,
        "total_score": display_final_score,
        "level": level,
        "teacher_comment": teacher_comment,
        "details": details,
        "competency_scores": competency_scores,
        "records": records,
    }

    if persist and display_final_score is not None:
        SecondarySubjectResult.objects.update_or_create(
            student=student,
            academic_class=academic_class,
            subject=subject,
            defaults={
                "ca_average": display_ca_score or Decimal("0.00"),
                "exam_score": display_exam_score or Decimal("0.00"),
                "final_score": display_final_score,
                "grade": level["short_label"] or "-",
                "descriptor": level["descriptor"],
            },
        )

    return result_payload


def build_subject_rows(student, academic_class, policy=None, persist=False):
    policy = policy or get_policy_for_date(
        academic_class.section,
        target_date=getattr(academic_class.term, "end_date", None),
    )
    subject_rows = []
    competency_scores = defaultdict(list)
    project_rows = []

    for subject in _student_subjects_for_class(student, academic_class):
        row = compute_subject_result(student, academic_class, subject, policy=policy, persist=persist)
        subject_rows.append(row)
        for competency_id, scores in row["competency_scores"].items():
            competency_scores[competency_id].extend(scores)
        for detail in row["details"]:
            if detail["task_type_code"] in PROJECT_TASK_TYPES:
                project_rows.append(
                    {
                        "title": detail["task_title"],
                        "task_type": detail["task_type"],
                        "subject_name": subject.name,
                        "level": get_level_for_score(detail["normalized_score"], policy=policy)
                        if detail["normalized_score"] is not None
                        else get_level_for_score(None, policy=policy),
                        "teacher_comment": detail["teacher_comment"],
                        "evidence_reference": detail["evidence_reference"],
                    }
                )

    subject_rows.sort(key=lambda item: item["subject_name"])
    return subject_rows, competency_scores, project_rows


def build_competency_rows(academic_class, competency_scores, policy=None):
    competencies = (
        SecondaryCompetency.objects.filter(subject_links__section=academic_class.section)
        .distinct()
        .order_by("code")
    )
    rows = []
    for competency in competencies:
        scores = competency_scores.get(competency.id, [])
        score_percent = (sum(scores) / Decimal(len(scores))) if scores else None
        display_score = _round_for_policy(score_percent, policy) if score_percent is not None else None
        rows.append(
            {
                "name": competency.name,
                "score_percent": display_score,
                "progress_percent": float(display_score or Decimal("0.00")),
                "level": get_level_for_score(display_score, policy=policy),
            }
        )
    return rows


def build_attendance_snapshot(student, academic_class):
    records = list(
        AttendanceRecord.objects.filter(
            student=student,
            session__class_stream__academic_class=academic_class,
        ).select_related("session")
    )
    total_records = len(records)
    effective_statuses = {
        AttendanceStatus.PRESENT,
        AttendanceStatus.LATE,
        AttendanceStatus.EXCUSED,
    }
    effective_count = sum(1 for record in records if record.status in effective_statuses)
    attendance_percent = (
        (Decimal(effective_count) / Decimal(total_records)) * Decimal("100")
        if total_records
        else Decimal("0.00")
    )
    remarks = []
    for record in records:
        remark = (record.remarks or "").strip()
        if remark and remark not in remarks:
            remarks.append(remark)
    if attendance_percent >= Decimal("90"):
        participation_level = "Excellent"
    elif attendance_percent >= Decimal("75"):
        participation_level = "Consistent"
    elif attendance_percent >= Decimal("60"):
        participation_level = "Needs Support"
    else:
        participation_level = "At Risk"

    return {
        "attendance_percent": _quantize(attendance_percent),
        "participation_level": participation_level,
        "total_records": total_records,
        "discipline_remarks": " | ".join(remarks[:3]),
    }


def _next_class_label(academic_class):
    code = (academic_class.Class.code or "").upper()
    next_map = {
        "S1": "S2",
        "S2": "S3",
        "S3": "S4",
        "O1": "O2",
        "O2": "O3",
        "O3": "O4",
    }
    next_code = next_map.get(code)
    if not next_code:
        return "Completed Lower Secondary"
    next_class = Class.objects.filter(section=academic_class.section, code=next_code).first()
    return next_class.name if next_class else next_code


def build_promotion_decision(academic_class, mean_score, attendance_snapshot, has_project_evidence):
    code = (academic_class.Class.code or "").upper()
    attendance_percent = _to_decimal(attendance_snapshot.get("attendance_percent"))
    minimum_attendance = _to_decimal(AttendancePolicy.load().minimum_attendance_percent)

    if mean_score is None:
        return {
            "title": "Pending Evidence",
            "condition": "Capture learning evidence and end-of-term exam results before promotion can be recommended.",
            "target_label": _next_class_label(academic_class),
            "tone": "pending",
        }

    if code in {"S4", "O4"}:
        return {
            "title": "Completing Lower Secondary",
            "condition": (
                "Eligible for transition after UNEB and project requirements are satisfied."
                if has_project_evidence
                else "Project evidence is still incomplete for certificate readiness."
            ),
            "target_label": "Transition to Senior 5 / TVET",
            "tone": "graduating",
        }

    if attendance_percent < minimum_attendance:
        return {
            "title": "Conditional Promotion",
            "condition": f"Attendance is below the school minimum of {minimum_attendance}%.",
            "target_label": _next_class_label(academic_class),
            "tone": "conditional",
        }

    if mean_score >= Decimal("70"):
        title = "Full Promotion"
        tone = "full"
        condition = "Learner met the expected competency threshold across the term."
    elif mean_score >= Decimal("50"):
        title = "Conditional Promotion"
        tone = "conditional"
        condition = "Promote with targeted support in weaker learning areas."
    else:
        title = "Repeat / Intensive Remediation"
        tone = "repeat"
        condition = "Learner needs structured remediation before progressing."

    return {
        "title": title,
        "condition": condition,
        "target_label": _next_class_label(academic_class),
        "tone": tone,
    }


def build_class_ranking_map(academic_class, policy=None):
    ranking_rows = []
    for student in get_students_for_academic_class(academic_class):
        subject_rows, _, _ = build_subject_rows(student, academic_class, policy=policy, persist=False)
        scores = [row["total_score"] for row in subject_rows if row["total_score"] is not None]
        average = (sum(scores) / Decimal(len(scores))) if scores else None
        if average is not None:
            ranking_rows.append((student.id, average))

    ranking_rows.sort(key=lambda item: item[1], reverse=True)
    ranking_map = {}
    for index, (student_id, average) in enumerate(ranking_rows, start=1):
        ranking_map[student_id] = {"position": index, "average": _quantize(average)}
    return ranking_map


def persist_secondary_results(student, academic_class, subject_rows, mean_score, ranking_map, project_rows):
    ranked_subjects = [
        row for row in subject_rows if row["total_score"] is not None and row["subject"] is not None
    ]
    ranked_subjects.sort(key=lambda row: row["total_score"], reverse=True)
    best_subject_ids = {row["subject"].id for row in ranked_subjects[:8]}

    for row in subject_rows:
        if row["total_score"] is None:
            continue
        is_explicit_best_8 = row["subject"].id in best_subject_ids
        SecondarySubjectResult.objects.update_or_create(
            student=student,
            academic_class=academic_class,
            subject=row["subject"],
            defaults={
                "ca_average": row["ca_score"] or Decimal("0.00"),
                "exam_score": row["eot_score"] or Decimal("0.00"),
                "final_score": row["total_score"],
                "grade": row["level"]["short_label"] or "-",
                "descriptor": row["level"]["descriptor"],
                "is_best_8": is_explicit_best_8,
            },
        )

    scored_subjects = [row["total_score"] for row in ranked_subjects]
    best_8_average = (
        sum(scored_subjects[:8]) / Decimal(min(len(scored_subjects), 8))
        if scored_subjects
        else None
    )
    ranking = ranking_map.get(student.id, {})
    SecondaryOverallResult.objects.update_or_create(
        student=student,
        academic_class=academic_class,
        defaults={
            "overall_average": mean_score or Decimal("0.00"),
            "best_8_average": _quantize(best_8_average) if best_8_average is not None else None,
            "total_subjects": len(ranked_subjects),
            "total_points": _quantize(sum(scored_subjects)) if scored_subjects else Decimal("0.00"),
            "position": ranking.get("position"),
            "qualifies_for_certificate": bool(project_rows),
        },
    )


def build_cbc_term_report_context(request, academic_class, student):
    policy = get_policy_for_date(
        academic_class.section,
        target_date=getattr(academic_class.term, "end_date", None),
    )
    subject_rows, competency_scores, project_rows = build_subject_rows(
        student,
        academic_class,
        policy=policy,
        persist=False,
    )
    competency_rows = build_competency_rows(academic_class, competency_scores, policy=policy)
    attendance_snapshot = build_attendance_snapshot(student, academic_class)
    ranking_map = build_class_ranking_map(academic_class, policy=policy)

    scores = [row["total_score"] for row in subject_rows if row["total_score"] is not None]
    mean_score = _quantize(sum(scores) / Decimal(len(scores))) if scores else None
    overall_level = get_level_for_score(mean_score, policy=policy)
    class_size = get_students_for_academic_class(academic_class).count()
    ranking = ranking_map.get(student.id)
    position_label = f"{ranking['position']} / {class_size}" if ranking else "-"
    promotion_decision = build_promotion_decision(
        academic_class,
        mean_score,
        attendance_snapshot,
        has_project_evidence=bool(project_rows),
    )

    class_stream = (
        AcademicClassStream.objects.filter(academic_class=academic_class, stream=student.stream)
        .select_related("class_teacher")
        .first()
    )
    if class_stream is None:
        class_stream = AcademicClassStream.objects.filter(academic_class=academic_class).select_related(
            "class_teacher"
        ).first()

    remark = ReportRemark.objects.filter(student=student, term=academic_class.term).first()
    head_teacher_signature = Signature.objects.filter(position="HEAD TEACHER").first()
    class_teacher_name = str(class_stream.class_teacher) if class_stream and class_stream.class_teacher_id else ""
    class_teacher_signature = class_stream.class_teacher_signature if class_stream else None
    school = SchoolSetting.load()

    persist_secondary_results(
        student,
        academic_class,
        subject_rows,
        mean_score,
        ranking_map,
        project_rows,
    )

    return {
        "report_ready": True,
        "school": school,
        "selected_academic_class": academic_class,
        "selected_student": student,
        "summary": {
            "overall_level": overall_level,
            "mean_score": mean_score,
            "attendance_percent": attendance_snapshot["attendance_percent"],
            "position_label": position_label,
            "class_size": class_size,
        },
        "subject_rows": subject_rows,
        "competency_rows": competency_rows,
        "project_rows": project_rows,
        "attendance_snapshot": attendance_snapshot,
        "promotion_decision": promotion_decision,
        "class_teacher_remark": getattr(remark, "class_teacher_remark", ""),
        "head_teacher_remark": getattr(remark, "head_teacher_remark", ""),
        "class_teacher_name": class_teacher_name,
        "class_teacher_signature": class_teacher_signature,
        "head_teacher_signature": head_teacher_signature,
        "ca_weight_label": _to_decimal(getattr(policy, "ca_weight", Decimal("20.00"))),
        "exam_weight_label": _to_decimal(getattr(policy, "exam_weight", Decimal("80.00"))),
        "generated_at": timezone.now(),
    }


def build_result_preview(student, academic_class, subject, exam_score, policy=None):
    policy = policy or get_policy_for_date(
        academic_class.section,
        target_date=getattr(academic_class.term, "end_date", None),
    )
    payload = compute_subject_result(
        student,
        academic_class,
        subject,
        policy=policy,
        exam_score=exam_score,
        persist=True,
    )
    ca_score = payload["ca_score"]
    resolved_exam_score = payload["eot_score"]
    ca_weight = _to_decimal(getattr(policy, "ca_weight", Decimal("20.00")))
    exam_weight = _to_decimal(getattr(policy, "exam_weight", Decimal("80.00")))
    ca_contribution = ((ca_score or Decimal("0.00")) * ca_weight) / Decimal("100")
    exam_contribution = ((resolved_exam_score or Decimal("0.00")) * exam_weight) / Decimal("100")
    return {
        "ca_score": ca_score,
        "exam_score": resolved_exam_score,
        "ca_contribution": _quantize(ca_contribution),
        "exam_contribution": _quantize(exam_contribution),
        "final_score": payload["total_score"],
        "grade": payload["level"]["short_label"],
        "descriptor": payload["level"]["descriptor"],
        "policy": policy,
    }, payload["records"]


def save_exam_results(assessment, submitted_scores):
    students = list(get_students_for_subject(assessment.academic_class, assessment.subject))
    existing_results = {
        result.student_id: result for result in Result.objects.filter(assessment=assessment)
    }
    saved = 0
    deleted = 0
    errors = []

    for student in students:
        raw_value = (submitted_scores.get(str(student.id)) or "").strip()
        result = existing_results.get(student.id)
        if not raw_value:
            if result is not None:
                result.delete()
                deleted += 1
            continue

        try:
            score = Decimal(raw_value)
        except (InvalidOperation, TypeError, ValueError):
            errors.append(f"{student.student_name}: invalid score.")
            continue

        if score < 0 or score > assessment.out_of:
            errors.append(
                f"{student.student_name}: score must be between 0 and {assessment.out_of}."
            )
            continue

        if result is None:
            result = Result(assessment=assessment, student=student)
        result.score = score
        result.status = "DRAFT"
        result.save()
        saved += 1

    return {
        "students": students,
        "saved": saved,
        "deleted": deleted,
        "errors": errors,
    }


def get_alevel_policy_for_date(section, target_date=None):
    return get_policy_for_date(section, target_date=target_date, level=UPPER_POLICY_LEVEL)


def _select_best_alevel_records(records):
    if not records:
        return None, []

    if any(record.module_id for record in records):
        best_by_module = {}
        for record in records:
            key = record.module_id or f"component-{record.component_type}"
            existing = best_by_module.get(key)
            if existing is None or (
                record.points_awarded,
                record.attempt_no,
                record.assessed_on,
                record.id,
            ) > (
                existing.points_awarded,
                existing.attempt_no,
                existing.assessed_on,
                existing.id,
            ):
                best_by_module[key] = record
        selected_records = sorted(
            best_by_module.values(),
            key=lambda row: (
                row.module.module_order if row.module_id else 0,
                row.module.code if row.module_id else "",
                row.attempt_no,
            ),
        )
        average_point = sum(_to_decimal(record.points_awarded) for record in selected_records) / Decimal(
            len(selected_records)
        )
        return average_point, selected_records

    best_record = max(
        records,
        key=lambda row: (
            row.points_awarded,
            row.attempt_no,
            row.assessed_on,
            row.id,
        ),
    )
    return _to_decimal(best_record.points_awarded), [best_record]


def build_alevel_result_preview(student, subject, policy=None, persist=False):
    policy = policy or get_alevel_policy_for_date(
        subject.section,
        target_date=timezone.localdate(),
    )
    record_queryset = (
        ALevelAssessmentRecord.objects.filter(student=student, subject=subject)
        .select_related("module", "academic_year")
        .order_by("-assessed_on", "-attempt_no", "-id")
    )
    if student.academic_year_id:
        record_queryset = record_queryset.filter(academic_year_id=student.academic_year_id)

    weights = list(
        ALevelComponentWeight.objects.filter(policy=policy, subject=subject).order_by("component_type")
    ) if policy else []
    if not weights:
        observed_types = sorted(
            set(record_queryset.values_list("component_type", flat=True))
        )
        if observed_types:
            equal_weight = Decimal("100.00") / Decimal(len(observed_types))
            weights = [
                ALevelComponentWeight(
                    policy=policy,
                    subject=subject,
                    component_type=component_type,
                    weight=equal_weight,
                    is_required=False,
                )
                for component_type in observed_types
            ]

    component_rows = []
    selected_records = []
    modular_breakdown = []
    weighted_point = Decimal("0.00")

    for weight in weights:
        component_records = list(record_queryset.filter(component_type=weight.component_type))
        point_value, chosen_records = _select_best_alevel_records(component_records)
        contribution = None
        if point_value is not None:
            contribution = (_to_decimal(point_value) * _to_decimal(weight.weight)) / Decimal("100")
            weighted_point += contribution
            selected_records.extend(chosen_records)
            for record in chosen_records:
                if record.module_id:
                    modular_breakdown.append(
                        {
                            "module_code": record.module.code,
                            "module_name": record.module.name,
                            "attempt_no": record.attempt_no,
                            "competency_code": record.competency_code or "-",
                            "points": _quantize(record.points_awarded),
                        }
                    )

        component_rows.append(
            {
                "component_type": weight.get_component_type_display(),
                "point_value": _quantize(point_value) if point_value is not None else None,
                "weight": _quantize(weight.weight),
                "contribution": _quantize(contribution) if contribution is not None else None,
            }
        )

    final_scale = None
    if policy:
        final_scale = (
            policy.alevel_scales.filter(
                min_weighted_point__lte=weighted_point,
                max_weighted_point__gte=weighted_point,
            )
            .order_by("display_order", "-min_weighted_point")
            .first()
        )

    result = {
        "weighted_point": _quantize(weighted_point) if component_rows else None,
        "final_competency": final_scale.code if final_scale else "-",
        "final_descriptor": final_scale.descriptor if final_scale else "No scale matched the weighted point.",
        "modular_breakdown": modular_breakdown,
    }

    selected_records = sorted(
        {record.id: record for record in selected_records}.values(),
        key=lambda row: (row.assessed_on, row.id),
        reverse=True,
    )
    if persist and result["weighted_point"] is not None and student.academic_year_id:
        ALevelSubjectResult.objects.update_or_create(
            student=student,
            subject=subject,
            academic_year_id=student.academic_year_id,
            defaults={
                "policy": policy,
                "weighted_point": result["weighted_point"],
                "final_competency": result["final_competency"],
                "final_descriptor": result["final_descriptor"],
            },
        )

    return result, component_rows, selected_records


def build_uneb_batch_items(batch, candidate_class_id):
    if candidate_class_id:
        batch.candidate_class_id = candidate_class_id
        batch.save(update_fields=["candidate_class"])
    if not batch.candidate_class_id:
        return {"created": 0, "updated": 0, "deleted": 0}

    academic_classes = list(
        AcademicClass.objects.filter(
            academic_year=batch.academic_year,
            section=batch.section,
            Class=batch.candidate_class,
        )
    )
    if not academic_classes:
        batch.items.all().delete()
        return {"created": 0, "updated": 0, "deleted": 0}

    student_ids = (
        ClassRegister.objects.filter(academic_class_stream__academic_class__in=academic_classes)
        .values_list("student_id", flat=True)
        .distinct()
    )
    students = Student.objects.filter(id__in=student_ids).order_by("student_name")

    existing_map = {
        (item.student_id, item.subject_id): item
        for item in batch.items.select_related("student", "subject")
    }
    seen_keys = set()
    created = 0
    updated = 0

    for student in students:
        enrollment_subject_ids = list(
            StudentSubjectEnrollment.objects.filter(
                academic_class__in=academic_classes,
                student=student,
                is_active=True,
            ).values_list("subject_id", flat=True)
        )
        if enrollment_subject_ids:
            subject_ids = sorted(set(enrollment_subject_ids))
        else:
            subject_ids = (
                ContinuousAssessmentRecord.objects.filter(
                    student=student,
                    task__academic_class__in=academic_classes,
                    task__uneb_eligible=True,
                )
                .exclude(moderation_status=ContinuousAssessmentRecord.ModerationStatus.REJECTED)
                .values_list("task__subject_id", flat=True)
                .distinct()
            )
        for subject in Subject.objects.filter(id__in=subject_ids).order_by("name"):
            records = [
                record
                for record in ContinuousAssessmentRecord.objects.filter(
                    student=student,
                    task__academic_class__in=academic_classes,
                    task__subject=subject,
                    task__uneb_eligible=True,
                )
                .exclude(moderation_status=ContinuousAssessmentRecord.ModerationStatus.REJECTED)
                .select_related("task")
            ]
            ca_mark = calculate_ca_average(records)
            if ca_mark is None:
                continue

            statuses = {record.moderation_status for record in records}
            derived_status = _derive_uneb_item_moderation_status(statuses)
            rounded_ca_mark = _round_for_policy(ca_mark, None)
            evidence_count = sum(1 for record in records if (record.evidence_reference or "").strip())
            defaults = {
                "ca_mark": rounded_ca_mark,
                "source_task_count": len(records),
                "evidence_count": evidence_count,
            }
            item = existing_map.get((student.id, subject.id))
            if item:
                existing_status = item.moderation_status
                existing_final_ca_mark = item.final_ca_mark
                for field, value in defaults.items():
                    setattr(item, field, value)
                if item.is_locked or existing_status == UNEBSubmissionItem.ModerationStatus.LOCKED:
                    item.is_locked = True
                    item.moderation_status = UNEBSubmissionItem.ModerationStatus.LOCKED
                    if item.final_ca_mark is None:
                        item.final_ca_mark = existing_final_ca_mark or rounded_ca_mark
                elif existing_status in {
                    UNEBSubmissionItem.ModerationStatus.MODERATED,
                    UNEBSubmissionItem.ModerationStatus.APPROVED,
                    UNEBSubmissionItem.ModerationStatus.REJECTED,
                }:
                    item.moderation_status = existing_status
                    item.final_ca_mark = existing_final_ca_mark if existing_final_ca_mark is not None else rounded_ca_mark
                else:
                    item.moderation_status = derived_status
                    item.final_ca_mark = rounded_ca_mark
                item.save()
                updated += 1
            else:
                UNEBSubmissionItem.objects.create(
                    batch=batch,
                    student=student,
                    subject=subject,
                    final_ca_mark=rounded_ca_mark,
                    moderation_status=derived_status,
                    **defaults,
                )
                created += 1
            seen_keys.add((student.id, subject.id))

    stale_items = [
        item.id
        for key, item in existing_map.items()
        if key not in seen_keys
    ]
    deleted = 0
    if stale_items:
        deleted = len(stale_items)
        batch.items.filter(id__in=stale_items).delete()

    return {"created": created, "updated": updated, "deleted": deleted}
