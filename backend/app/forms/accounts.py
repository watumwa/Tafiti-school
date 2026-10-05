# forms.py
from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()
from django.contrib.auth.forms import AuthenticationForm
from app.models import StaffAccount
from app.models.staffs import Staff

class StaffAccountForm(forms.Form):
    
    staff = forms.ModelChoiceField(
        queryset=Staff.objects.exclude(staffaccount__isnull=False),
        label="Select Staff"
    )
class CustomLoginForm(AuthenticationForm):
    class Meta:
        model = User
        fields = ['username', 'password']

class RoleSwitchForm(forms.ModelForm):
    class Meta:
        model = StaffAccount
        fields = ['role']