from django.forms import ModelForm, DateInput
from crispy_forms.helper import FormHelper
from django import forms
from app.models.staffs import Role, Staff

class StaffForm(ModelForm):
    
    class Meta:
        model = Staff
        fields = ("__all__")
        widgets = {
            'roles': forms.CheckboxSelectMultiple,  # Allows multiple roles to be selected
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['roles'].queryset = Role.objects.filter(is_active=True).order_by('name')
        
        self.Helper = FormHelper()
        self.fields["birth_date"].widget = DateInput(attrs={
                    "type": "date"})
        self.fields["hire_date"].widget = DateInput(attrs={
                    "type": "date"})
        
        

        

        
