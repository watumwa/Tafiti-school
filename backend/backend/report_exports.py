from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from app.models import AcademicClass, ClassRegister, Result
from app.utils.pdf_utils import generate_student_report_pdf

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context


EXPORT_ROLES = {"Admin", "Head Teacher", "Director of Studies", "Class Teacher"}


def _role(request):
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _safe_name(value):
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value)).strip("_") or "student"


class ReportCardBulkExportAPIView(WorkspaceBaseAPIView):
    def get(self, request, class_id: int):
        if not request.user.is_superuser and _role(request) not in EXPORT_ROLES:
            return Response({"detail": "Your current role cannot export class report cards."}, status=status.HTTP_403_FORBIDDEN)
        try:
            academic_class = AcademicClass.objects.select_related("Class", "term", "academic_year").get(pk=class_id)
        except AcademicClass.DoesNotExist:
            return Response({"detail": "Academic class not found."}, status=status.HTTP_404_NOT_FOUND)

        students = []
        seen = set()
        for register in ClassRegister.objects.filter(
            academic_class_stream__academic_class=academic_class,
            student__is_active=True,
        ).select_related("student").order_by("student__student_name", "student__reg_no"):
            if register.student_id not in seen:
                seen.add(register.student_id)
                students.append(register.student)
        if not students:
            return Response({"detail": "There are no active students registered in this class."}, status=status.HTTP_404_NOT_FOUND)

        archive = BytesIO()
        exported = 0
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
            for student in students:
                verified = Result.objects.filter(
                    student=student,
                    assessment__academic_class=academic_class,
                    status="VERIFIED",
                ).select_related("assessment__subject", "assessment__assessment_type", "assessment__academic_class")
                if not verified.exists():
                    continue
                pdf = generate_student_report_pdf(student, verified)
                filename = f"{_safe_name(student.reg_no)}_{_safe_name(student.student_name)}.pdf"
                bundle.writestr(filename, pdf.getvalue())
                exported += 1
            bundle.writestr(
                "README.txt",
                f"Tafiti report card export\nClass: {academic_class.Class}\nTerm: {academic_class.term}\nAcademic year: {academic_class.academic_year}\nStudents exported: {exported}\n",
            )
        if not exported:
            return Response({"detail": "No verified student results are available for bulk export."}, status=status.HTTP_404_NOT_FOUND)

        archive.seek(0)
        response = HttpResponse(archive.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="report-cards-{_safe_name(academic_class.Class)}-{_safe_name(academic_class.term)}.zip"'
        return response
