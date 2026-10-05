from django import forms
from app.models.timetables import Classroom, TimeSlot

class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ['start_time', 'end_time']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class ClassroomForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = ["name", "location", "capacity"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        duplicate = Classroom.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists()
        if duplicate:
            raise forms.ValidationError("A classroom with this name already exists.")
        return name
