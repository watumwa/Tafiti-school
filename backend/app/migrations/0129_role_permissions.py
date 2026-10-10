from django.db import migrations, models
import django.db.models.deletion


MODULE_KEYS = (
    "students", "staff", "admissions", "parents", "classes", "subjects", "results",
    "attendance", "timetable", "fees", "finance", "library", "communication", "audit", "settings",
)


def _canonical(label):
    normalized = " ".join(str(label or "").strip().lower().replace("/", " ").split())
    aliases = {
        "administrator": "Admin",
        "head teacher": "Head Teacher",
        "headteacher": "Head Teacher",
        "head master": "Head Teacher",
        "headmaster": "Head Teacher",
        "director of studies": "Director of Studies",
        "dos": "Director of Studies",
        "class teacher": "Class Teacher",
        "admissions officer": "Admissions Officer",
        "library assistant": "Library Assistant",
        "support staff": "Support Staff",
    }
    return aliases.get(normalized, str(label or "").strip())


def seed_role_permissions(apps, schema_editor):
    Role = apps.get_model("app", "Role")
    RolePermission = apps.get_model("app", "RolePermission")

    defaults = {
        "Admin": set(MODULE_KEYS),
        "Head Teacher": set(MODULE_KEYS),
        "Director of Studies": {"students", "staff", "admissions", "parents", "classes", "subjects", "results", "attendance", "timetable", "communication", "audit"},
        "Bursar": {"students", "fees", "finance", "communication", "audit"},
        "Class Teacher": {"students", "classes", "subjects", "results", "attendance", "timetable", "communication"},
        "Teacher": {"students", "classes", "subjects", "results", "attendance", "timetable", "communication"},
        "Admissions Officer": {"students", "admissions", "communication"},
        "Librarian": {"students", "library", "communication"},
        "Library Assistant": {"students", "library", "communication"},
        "Support Staff": {"communication"},
        "Staff": {"communication"},
    }
    storage_names = {"Head Teacher": "Head master"}

    by_label = {}
    for role in Role.objects.all().order_by("id"):
        by_label.setdefault(_canonical(role.name), role)

    for label, allowed in defaults.items():
        role = by_label.get(label)
        if role is None:
            role = Role.objects.create(name=storage_names.get(label, label), is_system=True, is_active=True)
            by_label[label] = role
        elif not role.is_system:
            role.is_system = True
            role.save(update_fields=["is_system"])
        for module in MODULE_KEYS:
            RolePermission.objects.update_or_create(
                role=role,
                module=module,
                defaults={"allowed": module in allowed},
            )


class Migration(migrations.Migration):

    dependencies = [("app", "0128_payment_mobile_money_method")]

    operations = [
        migrations.AlterField(
            model_name="role",
            name="name",
            field=models.CharField(max_length=50, unique=True),
        ),
        migrations.AddField(
            model_name="role",
            name="description",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="role",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="role",
            name="is_system",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="RolePermission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("module", models.CharField(max_length=40)),
                ("allowed", models.BooleanField(default=False)),
                ("role", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="module_permissions", to="app.role")),
            ],
            options={
                "verbose_name": "Role permission",
                "verbose_name_plural": "Role permissions",
                "ordering": ("role_id", "module"),
            },
        ),
        migrations.AddConstraint(
            model_name="rolepermission",
            constraint=models.UniqueConstraint(fields=("role", "module"), name="role_permission_once_per_module"),
        ),
        migrations.RunPython(seed_role_permissions, migrations.RunPython.noop),
    ]
