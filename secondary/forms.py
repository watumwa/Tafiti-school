from decimal import Decimal

from django import forms
from django.db.models import Q

from app.models.classes import Term
from app.models.results import Assessment
from app.models.school_settings import AcademicYear, SchoolSetting
from app.services.level_scope import (
    get_level_academic_classes_queryset,
    get_level_classes_queryset,
    get_level_sections_queryset,
    get_level_students_queryset,
    get_level_subjects_queryset,
)
from secondary.services import evaluate_subject_load, get_secondary_exam_assessment_types
from secondary.models import (
    ALevelAssessmentRecord,
    ALevelCompetencyScale,
    ALevelComponentWeight,
    ALevelSubjectModule,
    ContinuousAssessmentTask,
    SecondaryCompetency,
    SecondaryComputationPolicy,
    SecondaryGradeBand,
    StudentSubjectEnrollment,
    SubjectCompetency,
    UNEBSubmissionBatch,
)


LOWER_LEVEL = SchoolSetting.EducationLevel.SECONDARY_LOWER


class SecondaryPolicyForm(forms.ModelForm):
    class Meta:
        model = SecondaryComputationPolicy
        fields = (
            "name",
            "section",
            "ca_weight",
            "exam_weight",
            "rounding_mode",
            "effective_from",
            "effective_to",
            "is_active",
        )
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "effective_to": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def __init__(self, *args, active_level=LOWER_LEVEL, **kwargs):
        super().__init__(*args, **kwargs)
        section_queryset = get_level_sections_queryset(active_level=active_level)
        class_section_ids = get_level_classes_queryset(active_level=active_level).values_list(
            "section_id",
            flat=True,
        )
        if class_section_ids:
            section_queryset = section_queryset.filter(id__in=class_section_ids)
        self.fields["section"].queryset = section_queryset.distinct()
        if active_level == SchoolSetting.EducationLevel.SECONDARY_UPPER:
            self.fields["ca_weight"].initial = Decimal("0.00")
            self.fields["exam_weight"].initial = Decimal("100.00")


class SecondaryGradeBandForm(forms.ModelForm):
    class Meta:
        model = SecondaryGradeBand
        fields = ("grade", "descriptor", "min_score", "max_score", "display_order")


class SecondaryCompetencyForm(forms.ModelForm):
    class Meta:
        model = SecondaryCompetency
        fields = ("code", "name", "description", "is_active")


class SubjectCompetencyForm(forms.ModelForm):
    class Meta:
        model = SubjectCompetency
        fields = ("section", "subject", "competency", "is_core")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        class_section_ids = get_level_classes_queryset(active_level=LOWER_LEVEL).values_list(
            "section_id",
            flat=True,
        )
        self.fields["section"].queryset = get_level_sections_queryset(active_level=LOWER_LEVEL).filter(
            id__in=class_section_ids
        ).distinct()
        self.fields["subject"].queryset = get_level_subjects_queryset(active_level=LOWER_LEVEL)
        self.fields["competency"].queryset = SecondaryCompetency.objects.order_by("code")


class ContinuousAssessmentTaskForm(forms.ModelForm):
    class Meta:
        model = ContinuousAssessmentTask
        fields = (
            "academic_class",
            "term",
            "subject",
            "subject_competency",
            "title",
            "task_type",
            "weight",
            "max_score",
            "assigned_date",
            "evidence_required",
            "uneb_eligible",
        )
        widgets = {
            "assigned_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["academic_class"].queryset = get_level_academic_classes_queryset(active_level=LOWER_LEVEL)
        self.fields["term"].queryset = Term.objects.select_related("academic_year").order_by(
            "-academic_year__academic_year",
            "-start_date",
        )
        self.fields["subject"].queryset = get_level_subjects_queryset(active_level=LOWER_LEVEL)
        self.fields["subject_competency"].queryset = SubjectCompetency.objects.select_related(
            "subject",
            "competency",
        ).order_by("subject__name", "competency__code")


class UNEBSubmissionBatchForm(forms.ModelForm):
    class Meta:
        model = UNEBSubmissionBatch
        fields = ("title", "section", "academic_year", "candidate_class", "notes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        class_section_ids = get_level_classes_queryset(active_level=LOWER_LEVEL).values_list(
            "section_id",
            flat=True,
        )
        self.fields["section"].queryset = get_level_sections_queryset(active_level=LOWER_LEVEL).filter(
            id__in=class_section_ids
        ).distinct()
        self.fields["academic_year"].queryset = AcademicYear.objects.order_by("-academic_year")
        self.fields["candidate_class"].queryset = get_level_classes_queryset(active_level=LOWER_LEVEL)


class StudentSubjectEnrollmentForm(forms.ModelForm):
    class Meta:
        model = StudentSubjectEnrollment
        fields = ("academic_class", "student", "subject", "is_compulsory", "is_active", "notes")

    def __init__(self, *args, academic_class=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["academic_class"].queryset = get_level_academic_classes_queryset(active_level=LOWER_LEVEL)
        self.fields["subject"].queryset = get_level_subjects_queryset(active_level=LOWER_LEVEL)
        if academic_class is not None:
            self.initial.setdefault("academic_class", academic_class)
            self.fields["student"].queryset = get_level_students_queryset(active_level=LOWER_LEVEL).filter(
                Q(
                    classregister__academic_class_stream__academic_class=academic_class
                )
                | Q(current_class=academic_class.Class)
            ).distinct().order_by("student_name")
            self.fields["subject"].queryset = self.fields["subject"].queryset.filter(
                section=academic_class.section
            )
        else:
            self.fields["student"].queryset = get_level_students_queryset(active_level=LOWER_LEVEL)

    def clean(self):
        cleaned_data = super().clean()
        academic_class = cleaned_data.get("academic_class")
        student = cleaned_data.get("student")
        subject = cleaned_data.get("subject")
        is_active = cleaned_data.get("is_active", True)
        is_compulsory = cleaned_data.get("is_compulsory", False)

        if not academic_class or not student or not subject:
            return cleaned_data

        subject_type = (subject.type or "").strip().lower()
        if subject_type == "core":
            cleaned_data["is_compulsory"] = True
        elif is_compulsory:
            self.add_error("is_compulsory", "Elective subjects cannot be marked as compulsory.")

        status = evaluate_subject_load(
            academic_class,
            student,
            extra_subject=subject,
            extra_subject_is_active=is_active,
        )
        for issue in status["blocking_issues"]:
            self.add_error("subject", issue)

        return cleaned_data


class SecondaryExamAssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ("academic_class", "assessment_type", "subject", "date", "out_of", "is_done")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["academic_class"].queryset = get_level_academic_classes_queryset(active_level=LOWER_LEVEL)
        self.fields["subject"].queryset = get_level_subjects_queryset(active_level=LOWER_LEVEL)
        self.fields["assessment_type"].queryset = get_secondary_exam_assessment_types()

    def clean(self):
        cleaned_data = super().clean()
        academic_class = cleaned_data.get("academic_class")
        subject = cleaned_data.get("subject")
        assessment_type = cleaned_data.get("assessment_type")
        out_of = cleaned_data.get("out_of")

        if academic_class and subject and academic_class.section_id != subject.section_id:
            self.add_error("subject", "Selected subject does not belong to the chosen academic class section.")

        if assessment_type and not get_secondary_exam_assessment_types().filter(id=assessment_type.id).exists():
            self.add_error("assessment_type", "Choose an end-of-term exam assessment type.")

        if out_of is not None and out_of <= 0:
            self.add_error("out_of", "Exam out-of value must be greater than zero.")

        return cleaned_data


class ALevelCompetencyScaleForm(forms.ModelForm):
    class Meta:
        model = ALevelCompetencyScale
        fields = (
            "code",
            "descriptor",
            "point_value",
            "min_weighted_point",
            "max_weighted_point",
            "display_order",
        )


class ALevelComponentWeightForm(forms.ModelForm):
    class Meta:
        model = ALevelComponentWeight
        fields = ("subject", "component_type", "weight", "is_required")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].queryset = get_level_subjects_queryset(
            active_level=SchoolSetting.EducationLevel.SECONDARY_UPPER
        )


class ALevelSubjectModuleForm(forms.ModelForm):
    class Meta:
        model = ALevelSubjectModule
        fields = ("subject", "code", "name", "module_order", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["subject"].queryset = get_level_subjects_queryset(
            active_level=SchoolSetting.EducationLevel.SECONDARY_UPPER
        )


class ALevelAssessmentRecordForm(forms.ModelForm):
    class Meta:
        model = ALevelAssessmentRecord
        fields = (
            "student",
            "subject",
            "component_type",
            "module",
            "attempt_no",
            "competency_code",
            "points_awarded",
            "assessed_on",
            "remarks",
        )
        widgets = {
            "assessed_on": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        upper_level = SchoolSetting.EducationLevel.SECONDARY_UPPER
        self.fields["student"].queryset = get_level_students_queryset(active_level=upper_level)
        self.fields["subject"].queryset = get_level_subjects_queryset(active_level=upper_level)
        self.fields["module"].queryset = ALevelSubjectModule.objects.select_related("subject").order_by(
            "subject__name",
            "module_order",
            "code",
        )


class ALevelResultPreviewForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=get_level_students_queryset(active_level=SchoolSetting.EducationLevel.SECONDARY_UPPER),
        label="Student",
    )
    subject = forms.ModelChoiceField(
        queryset=get_level_subjects_queryset(active_level=SchoolSetting.EducationLevel.SECONDARY_UPPER),
        label="Subject",
    )
    policy = forms.ModelChoiceField(
        queryset=SecondaryComputationPolicy.objects.filter(level=SecondaryComputationPolicy.Level.UPPER_SECONDARY)
        .select_related("section")
        .order_by("section__section_name", "-effective_from"),
        required=False,
        empty_label="Use active A-Level policy",
    )

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get("student")
        subject = cleaned_data.get("subject")
        policy = cleaned_data.get("policy")

        if student and subject and student.current_class_id and student.current_class.section_id != subject.section_id:
            self.add_error("subject", "Selected subject does not belong to the learner's current section.")

        if policy and subject and policy.section_id != subject.section_id:
            self.add_error("policy", "Selected policy does not belong to the subject section.")

        return cleaned_data


class ALevelSubjectResultFilterForm(forms.Form):
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.order_by("-academic_year"),
        required=False,
        empty_label="All academic years",
    )
    student = forms.ModelChoiceField(
        queryset=get_level_students_queryset(active_level=SchoolSetting.EducationLevel.SECONDARY_UPPER),
        required=False,
        empty_label="All students",
    )
    subject = forms.ModelChoiceField(
        queryset=get_level_subjects_queryset(active_level=SchoolSetting.EducationLevel.SECONDARY_UPPER),
        required=False,
        empty_label="All subjects",
    )


class SecondaryResultPreviewForm(forms.Form):
    academic_class = forms.ModelChoiceField(
        queryset=get_level_academic_classes_queryset(active_level=LOWER_LEVEL),
        label="Academic Class",
    )
    student = forms.ModelChoiceField(
        queryset=get_level_students_queryset(active_level=LOWER_LEVEL),
        label="Student",
    )
    subject = forms.ModelChoiceField(
        queryset=get_level_subjects_queryset(active_level=LOWER_LEVEL),
        label="Subject",
    )
    exam_score = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=100,
        required=False,
        help_text="Leave blank to use the captured end-of-term exam mark for this learner.",
    )
    policy = forms.ModelChoiceField(
        queryset=SecondaryComputationPolicy.objects.filter(level=SecondaryComputationPolicy.Level.LOWER_SECONDARY)
        .select_related("section")
        .order_by("section__section_name", "-effective_from"),
        required=False,
        empty_label="Use active section policy",
    )

    def clean(self):
        cleaned_data = super().clean()
        academic_class = cleaned_data.get("academic_class")
        student = cleaned_data.get("student")
        subject = cleaned_data.get("subject")
        policy = cleaned_data.get("policy")

        if academic_class and subject and academic_class.section_id != subject.section_id:
            self.add_error("subject", "Selected subject does not belong to the chosen academic class section.")

        if academic_class and student and student.current_class_id != academic_class.Class_id:
            self.add_error("student", "Selected student is not currently assigned to this class.")

        if policy and academic_class and policy.section_id != academic_class.section_id:
            self.add_error("policy", "Selected policy does not belong to the academic class section.")

        if academic_class and student and subject:
            enrollment_qs = StudentSubjectEnrollment.objects.filter(
                academic_class=academic_class,
                is_active=True,
            )
            if (
                (subject.type or "").strip().lower() != "core"
                and enrollment_qs.filter(subject=subject).exists()
                and not enrollment_qs.filter(student=student, subject=subject).exists()
            ):
                self.add_error("subject", "Selected learner is not enrolled for this subject in the chosen class.")

        return cleaned_data
