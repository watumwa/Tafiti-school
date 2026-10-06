from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from app.models import Message, ParentAccess, Staff


class ParentLoginForm(forms.Form):
    phone = forms.CharField(max_length=50, label="Registered guardian phone")
    password = forms.CharField(widget=forms.PasswordInput)


class ParentFirstPasswordForm(forms.Form):
    password = forms.CharField(min_length=8, widget=forms.PasswordInput, label="New password")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    def clean_password(self):
        password = self.cleaned_data["password"]
        try:
            validate_password(password)
        except ValidationError as exc:
            raise forms.ValidationError(list(exc.messages)) from exc
        return password

    def clean(self):
        data = super().clean()
        if data.get("password") and data.get("confirm_password") and data["password"] != data["confirm_password"]:
            self.add_error("confirm_password", "Passwords do not match.")
        return data


class ParentAccessPermissionsForm(forms.ModelForm):
    class Meta:
        model = ParentAccess
        fields = ("can_view_academics", "can_view_finance", "can_view_attendance")


class ParentConversationStartForm(forms.Form):
    teacher = forms.ModelChoiceField(queryset=Staff.objects.none())
    subject = forms.CharField(max_length=200, required=False)
    message = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, teachers=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = teachers if teachers is not None else Staff.objects.none()


class ParentMessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ("body",)
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Write a message…"})}
