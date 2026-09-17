from django.forms import ModelForm, DateInput
from crispy_forms.helper import FormHelper
from app.models.results import *
from app.models.results import Result,Assessment,AssessmentType,GradingSystem
from django import forms
from app.models.subjects import *
from app.models.classes import AcademicClass, ClassSubjectAllocation

class ResultForm(forms.ModelForm):
    class Meta:
        model = Result
        fields = ('score',)
 
class AssesmentTypeForm(ModelForm):
    
    class Meta:
        model = AssessmentType
        fields =("__all__")
        
        
        
class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        # Completion is derived from mark-entry/submission workflow, not chosen
        # while the assessment structure is created.
        fields = ('academic_class', 'assessment_type', 'subject', 'date', 'out_of')
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        }

    def clean(self):
        cleaned_data = super().clean()
        academic_class = cleaned_data.get("academic_class")
        subject = cleaned_data.get("subject")
        if academic_class and subject:
            allocated = ClassSubjectAllocation.objects.filter(
                academic_class_stream__academic_class=academic_class,
                subject=subject,
                is_active=True,
            ).exists()
            if not allocated:
                raise forms.ValidationError(
                    "This subject is not actively allocated to the selected class. "
                    "Complete Subject Allocation first."
                )
        return cleaned_data


class BulkAssessmentForm(forms.Form):
    academic_class = forms.ModelChoiceField(
        queryset=AcademicClass.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
        label="Academic class",
    )
    assessment_type = forms.ModelChoiceField(
        queryset=AssessmentType.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=True,
        label="Assessment type",
    )
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        required=True,
        label="Subjects",
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True,
        label="Date",
    )
    out_of = forms.IntegerField(
        initial=100,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=True,
        label="Out of",
    )
        
class GradingSystemForm(ModelForm):
    
    class Meta:
        model = GradingSystem
        fields =("__all__")


class ReportRemarkForm(forms.ModelForm):
    class Meta:
        model = ReportRemark
        fields = ['class_teacher_remark', 'head_teacher_remark']
        widgets = {
            'class_teacher_remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'head_teacher_remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
