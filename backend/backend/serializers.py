from __future__ import annotations

from rest_framework import serializers

from django.contrib.auth import get_user_model

from .models import FeeLedger, GradeMatrix, Student


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    assigned_roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "name",
            "role",
            "assigned_roles",
            "is_active",
        ]
        read_only_fields = ["id", "is_active"]

    def get_name(self, obj) -> str:
        return obj.get_full_name().strip() or obj.get_username()

    def get_role(self, obj) -> str:
        from .auth import serialize_user_context

        return serialize_user_context(obj)["role"]["label"]

    def get_assigned_roles(self, obj) -> list[str]:
        from .auth import assigned_role_labels

        return assigned_role_labels(obj)


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)
    login_context = serializers.ChoiceField(
        choices=("admin", "teacher", "bursar", "parent"),
        required=False,
    )


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=128)
    token = serializers.CharField(max_length=256)
    password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False, write_only=True)
    confirm_password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": ["Passwords do not match."]})
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    password = serializers.CharField(min_length=8, max_length=128, trim_whitespace=False, write_only=True)
    confirm_password = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": ["Passwords do not match."]})
        return attrs


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField(source="full_name")

    class Meta:
        model = Student
        fields = [
            "id",
            "student_code",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone_number",
            "grade_level",
            "class_name",
            "status",
            "parent_name",
            "parent_phone",
            "current_balance",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class GradeMatrixSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = GradeMatrix
        fields = [
            "id",
            "student",
            "student_name",
            "subject",
            "assessment_type",
            "academic_year",
            "term",
            "score",
            "total_score",
            "grade",
            "remarks",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

    def get_student_name(self, obj: GradeMatrix) -> str:
        return obj.student.full_name


class FeeLedgerSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = FeeLedger
        fields = [
            "id",
            "student",
            "student_name",
            "invoice_code",
            "term",
            "due_amount",
            "paid_amount",
            "balance_amount",
            "payment_status",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "balance_amount", "payment_status"]

    def get_student_name(self, obj: FeeLedger) -> str:
        return obj.student.full_name
