from django import forms

from app.models import LibraryBook, LibraryCopy, Staff, Student


class StudentBorrowerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, student):
        class_name = getattr(student.current_class, "code", "") or getattr(student.current_class, "name", "")
        stream = getattr(student.stream, "stream", "")
        return f"{student.reg_no} — {student.student_name} ({class_name} {stream})"


class StaffBorrowerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, staff):
        return f"{staff.first_name} {staff.last_name} — {staff.department}"


class LibraryBookForm(forms.ModelForm):
    class Meta:
        model = LibraryBook
        fields = "__all__"


class LibraryCopyForm(forms.ModelForm):
    class Meta:
        model = LibraryCopy
        fields = "__all__"


class LibraryIssueForm(forms.Form):
    student = StudentBorrowerChoiceField(queryset=Student.objects.none(), required=False)
    staff = StaffBorrowerChoiceField(queryset=Staff.objects.none(), required=False)
    copy = forms.ModelChoiceField(queryset=LibraryCopy.objects.none(), label="Available book copy")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["copy"].queryset = LibraryCopy.objects.filter(
            status=LibraryCopy.STATUS_AVAILABLE
        ).select_related("book")
        self.fields["student"].queryset = Student.objects.filter(is_active=True).select_related(
            "current_class", "stream"
        ).order_by("student_name")
        self.fields["staff"].queryset = Staff.objects.filter(staff_status="Active").order_by(
            "first_name", "last_name"
        )

    def clean(self):
        data = super().clean()
        if bool(data.get("student")) == bool(data.get("staff")):
            raise forms.ValidationError("Choose exactly one student or staff borrower.")
        return data


class LibraryReturnForm(forms.Form):
    condition = forms.ChoiceField(choices=(("good", "Good"), ("damaged", "Damaged")))
    damage_amount = forms.DecimalField(required=False, min_value=0, decimal_places=2)
    notes = forms.CharField(required=False, max_length=500)

    def clean(self):
        data = super().clean()
        if data.get("condition") == "damaged" and data.get("damage_amount") is None:
            self.add_error("damage_amount", "Enter the approved damage charge, including zero when no charge applies.")
        return data


class LibraryLostForm(forms.Form):
    amount = forms.DecimalField(min_value=0, decimal_places=2, label="Replacement charge")
    notes = forms.CharField(required=False, max_length=500)
