from pathlib import Path

from rest_framework import status
from rest_framework.response import Response

from app.constants import NATIONALITIES, RELIGIONS
from app.models import AcademicClass, AuditLog
from app.services.students import BulkStudentRegistrationError, bulk_student_registration

from .auth import canonical_role_label
from .workspace import WorkspaceBaseAPIView, _active_role


TEMPLATE_COLUMNS = [
    "Reg No (leave blank for auto)",
    "Student Name",
    "Gender",
    "Birth Date (YYYY-MM-DD)",
    "Nationality",
    "Religion",
    "Address",
    "Guardian",
    "Relationship",
    "Guardian Contact",
    "Academic Year",
    "Current Class",
    "Stream",
    "Term (1/2/3)",
]


class StudentBulkImportAPIView(WorkspaceBaseAPIView):
    allowed_roles = frozenset({"Admin", "Admissions Officer"})

    def _denied(self, request):
        role = canonical_role_label(_active_role(request))
        if request.user.is_superuser or role in self.allowed_roles:
            return None
        return Response(
            {"detail": "Only administrators and admissions officers can bulk-register students."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def get(self, request):
        denied = self._denied(request)
        if denied:
            return denied

        academic_class = (
            AcademicClass.objects.select_related("academic_year", "term", "Class")
            .prefetch_related("class_streams__stream")
            .filter(academic_year__is_current=True, term__is_current=True)
            .order_by("Class__name")
            .first()
        )
        sample = ["", "Jane Example", "F", "2015-02-20", "Ugandan", "Protestant", "Kampala", "Mary Example", "Mother", "0700000000", "", "P4", "Blue", "1"]
        if academic_class:
            stream = academic_class.class_streams.first()
            sample[10] = academic_class.academic_year.academic_year
            sample[11] = academic_class.Class.code
            sample[12] = stream.stream.stream if stream else ""
            sample[13] = academic_class.term.term

        return Response({
            "columns": TEMPLATE_COLUMNS,
            "sample": sample,
            "max_rows": 2000,
            "max_size_mb": 10,
            "accepted_gender": ["M", "F", "Male", "Female"],
            "accepted_nationalities": [value for value, _ in NATIONALITIES],
            "accepted_religions": [value for value, _ in RELIGIONS],
            "atomic": True,
        })

    def post(self, request):
        denied = self._denied(request)
        if denied:
            return denied

        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response(
                {"detail": "Choose a CSV file to upload.", "errors": ["No CSV file was received."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Path(uploaded.name).suffix.lower() != ".csv":
            return Response(
                {"detail": "Only CSV files are supported.", "errors": ["Save the workbook as CSV UTF-8 and try again."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if uploaded.size > 10 * 1024 * 1024:
            return Response(
                {"detail": "The CSV is larger than 10 MB.", "errors": ["Split the file into smaller batches."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = bulk_student_registration(uploaded)
        except BulkStudentRegistrationError as exc:
            return Response(
                {
                    "detail": "No students were imported. Correct every listed issue and upload again.",
                    "errors": exc.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        client_ip = forwarded_for.split(",")[0].strip() or request.META.get("REMOTE_ADDR") or None
        AuditLog.objects.create(
            user=request.user,
            username=request.user.get_username(),
            ip_address=client_ip,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:4000],
            method=request.method,
            path=request.get_full_path()[:512],
            action=AuditLog.ACTION_CREATE,
            object_repr="Bulk student registration",
            changes={"students_created": result["created_count"]},
            extra={"workflow": "student_csv_import", "file_name": uploaded.name},
        )
        return Response({
            "detail": f"Successfully registered {result['created_count']} student(s).",
            **result,
        }, status=status.HTTP_201_CREATED)
