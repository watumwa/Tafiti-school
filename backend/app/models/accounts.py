from django.contrib.auth import get_user_model
from django.db import models
from app.models.staffs import *

User = get_user_model()


class StaffAccount(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_account')
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    must_change_password = models.BooleanField(default=False)
    temporary_password_expires_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.user.username:
            first_initial = self.staff.first_name[0].upper()
            last_name = self.staff.last_name.lower()
            base_username = f"{first_initial}-{last_name}"
            unique_username = base_username
            counter = 1

            while User.objects.filter(username=unique_username).exists():
                unique_username = f"{base_username}{counter}"
                counter += 1

            self.user.username = unique_username

        # Never silently assign a shared/default credential from the model layer.
        # Account-creation services are responsible for issuing a one-time password.
        if not self.user.password:
            self.user.set_unusable_password()

        changed_fields = []
        if self.user.email != self.staff.email:
            self.user.email = self.staff.email
            changed_fields.append('email')
        if self.user.username and self.user.pk:
            changed_fields.append('username')
        if self.user.password and self.user.pk:
            changed_fields.append('password')
        if changed_fields:
            self.user.save(update_fields=list(dict.fromkeys(changed_fields)))

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.staff.first_name} {self.staff.last_name}"
