from __future__ import annotations

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from app.models import (
    Assessment,
    ClassRegister,
    ClassSubjectAllocation,
    GradingSystem,
    Result,
    ResultModeSetting,
    StaffAccount,
    VerificationDiscrepancy,
)
from app.services.results_sampling import (
    ensure_batch_for_assessment,
    record_correction,
    reset_batch_to_draft,
    submit_batch_for_verification,
)
from app.views.results import (
    _assessment_hub_queryset,
    _get_active_results_scope,
    _parse_score_or_raise,
    _submission_gate_errors,
)

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context


MARK_ENTRY_MANAGERS = {"Admin", "Head Teacher", "Director of Studies"}
UNLOCK_ROLES = {"Admin", "Director of Studies"}


def _active_role(request) -> str:
    return canonical_role_label(
        resolve_active_role(request.user, _token_context(request)).label
    )


def _staff_member(request):
    account = StaffAccount.objects.filter(user=request.user).select_related("staff", "role").first()
    return getattr(account, "staff", None)


def _teacher_can_enter(staff, assessment: Assessment) -> bool:
    if not staff:
        return False
    return ClassSubjectAllocation.objects.filter(
        is_active=True,
        subject_teacher=staff,
        academic_class_stream__academic_class=assessment.academic_class,
        subject=assessment.subject,
    ).exists()


def _permission_error(request, assessment: Assessment | None = None) -> str | None:
    if request.user.is_superuser:
        return None
    role = _active_role(request)
    if role == "Class Teacher":
        return "Class teachers cannot enter subject marks. Please contact the allocated subject teacher."
    if role == "Teacher":
        if assessment is None:
            return None
        if not _teacher_can_enter(_staff_member(request), assessment):
            return "You can only enter marks for subjects allocated to you in this class."
        return None
    if role in MARK_ENTRY_MANAGERS:
        return None
    return "Your current role cannot enter assessment marks."


def _students_for_assessment(assessment: Assessment):
    registers = ClassRegister.objects.filter(
        academic_class_stream__academic_class=assessment.academic_class,
        student__is_active=True,
    ).select_related("student")
    students = []
    seen = set()
    for register in registers:
        student = register.student
        if not student or student.pk in seen:
            continue
        seen.add(student.pk)
        students.append(student)
    students.sort(key=lambda student: ((student.student_name or "").casefold(), student.reg_no or ""))
    return students


def _assessment_payload(assessment: Assessment) -> dict:
    batch = getattr(assessment, "result_batch", None)
    status_value = batch.status if batch else "DRAFT"
    total_students = int(getattr(assessment, "total_students", 0) or 0)
    entered = int(getattr(assessment, "entered_results", 0) or 0)
    missing = max(total_students - entered, 0)
    progress = int(round((entered / total_students) * 100)) if total_students else 0

    if status_value == "FLAGGED":
        note = batch.rejection_reason or "Verification flagged this batch for correction."
    elif status_value == "PENDING":
        note = "Submitted and waiting for independent verification."
    elif status_value == "VERIFIED":
        note = "Verified and locked."
    elif entered == 0:
        note = "No marks entered yet."
    elif missing == 0:
        note = "All marks are entered and ready for submission."
    else:
        note = f"{missing} student(s) still need marks."

    return {
        "assessment_id": assessment.pk,
        "class": str(assessment.academic_class.Class),
        "class_id": assessment.academic_class_id,
        "term": str(assessment.academic_class.term),
        "academic_year": str(assessment.academic_class.academic_year),
        "subject": assessment.subject.name,
        "subject_id": assessment.subject_id,
        "assessment_type": assessment.assessment_type.name,
        "out_of": assessment.out_of,
        "date": assessment.date.isoformat(),
        "status": status_value,
        "status_label": dict(getattr(batch, "STATUS_CHOICES", [])).get(status_value, status_value.title()) if batch else "Draft",
        "entered": entered,
        "total_students": total_students,
        "missing": missing,
        "progress": progress,
        "note": note,
    }


def _hub_queryset_for(request):
    current_year, current_term = _get_active_results_scope()
    queryset = _assessment_hub_queryset()
    if current_year:
        queryset = queryset.filter(academic_class__academic_year=current_year)
    if current_term:
        queryset = queryset.filter(academic_class__term=current_term)

    role = _active_role(request)
    if not request.user.is_superuser and role == "Teacher":
        staff = _staff_member(request)
        if not staff:
            return queryset.none(), current_year, current_term
        queryset = queryset.filter(
            academic_class__class_streams__subjects__subject_teacher=staff,
            academic_class__class_streams__subjects__subject_id=F("subject_id"),
        ).distinct()
    elif not request.user.is_superuser and role == "Class Teacher":
        return queryset.none(), current_year, current_term
    elif not request.user.is_superuser and role not in MARK_ENTRY_MANAGERS:
        return queryset.none(), current_year, current_term

    return queryset, current_year, current_term


class MarksHubAPIView(WorkspaceBaseAPIView):
    def get(self, request):
        denial = _permission_error(request)
        role = _active_role(request)
        if denial and role != "Class Teacher":
            return Response({"detail": denial}, status=status.HTTP_403_FORBIDDEN)

        queryset, current_year, current_term = _hub_queryset_for(request)
        assessments = list(queryset.order_by(
            "academic_class__Class__name",
            "subject__name",
            "assessment_type__name",
            "date",
        )[:500])
        rows = [_assessment_payload(assessment) for assessment in assessments]
        return Response({
            "role": role,
            "can_enter": role != "Class Teacher" and not bool(denial),
            "blocked_reason": denial or "",
            "academic_year": str(current_year or ""),
            "term": str(current_term or ""),
            "metrics": {
                "assessments": len(rows),
                "need_marks": sum(1 for row in rows if row["status"] in {"DRAFT", "FLAGGED"} and row["missing"] > 0),
                "ready": sum(1 for row in rows if row["status"] == "DRAFT" and row["total_students"] > 0 and row["missing"] == 0),
                "flagged": sum(1 for row in rows if row["status"] == "FLAGGED"),
            },
            "assessments": rows,
        })


class MarksEntryAPIView(WorkspaceBaseAPIView):
    def _assessment(self, request, assessment_id: int):
        assessment = Assessment.objects.select_related(
            "academic_class__Class",
            "academic_class__term",
            "academic_class__academic_year",
            "subject",
            "assessment_type",
        ).get(pk=assessment_id)
        denial = _permission_error(request, assessment)
        if denial:
            return None, denial
        return assessment, None

    def get(self, request, assessment_id: int):
        try:
            assessment, denial = self._assessment(request, assessment_id)
        except Assessment.DoesNotExist:
            return Response({"detail": "Assessment not found."}, status=status.HTTP_404_NOT_FOUND)
        if denial:
            return Response({"detail": denial}, status=status.HTTP_403_FORBIDDEN)

        students = _students_for_assessment(assessment)
        batch = ensure_batch_for_assessment(assessment)
        existing = Result.objects.filter(
            assessment=assessment,
            student__is_active=True,
        ).select_related("student", "batch__submitted_by")
        result_by_student = {row.student_id: row for row in existing}

        rows = []
        for index, student in enumerate(students, start=1):
            result = result_by_student.get(student.pk)
            rows.append({
                "index": index,
                "student_id": student.pk,
                "display_id": student.display_student_id,
                "student": student.student_name,
                "score": str(result.score) if result else "",
                "grade": result.grade if result else "—",
                "points": str(result.points) if result else "—",
                "status": result.status if result else "MISSING",
                "audit": (
                    result.batch.submitted_by.username
                    if result and result.batch and result.batch.submitted_by
                    else ("Draft entry" if result else "—")
                ),
            })

        entered = len(result_by_student)
        gate_errors = _submission_gate_errors(assessment, students)
        role = _active_role(request)
        return Response({
            "assessment": {
                "id": assessment.pk,
                "class": str(assessment.academic_class.Class),
                "class_id": assessment.academic_class_id,
                "academic_year": str(assessment.academic_class.academic_year),
                "term": str(assessment.academic_class.term),
                "subject": assessment.subject.name,
                "subject_id": assessment.subject_id,
                "assessment_type": assessment.assessment_type.name,
                "date": assessment.date.isoformat(),
                "out_of": assessment.out_of,
            },
            "batch": {
                "id": batch.pk,
                "status": batch.status,
                "status_label": batch.get_status_display(),
                "rejection_reason": batch.rejection_reason or "",
                "submitted_by": str(batch.submitted_by or ""),
                "submitted_at": batch.submitted_at.isoformat() if batch.submitted_at else "",
            },
            "role": role,
            "mode": ResultModeSetting.get_mode(),
            "editable": batch.status in {"DRAFT", "FLAGGED"},
            "can_unlock": bool(
                batch.status == "VERIFIED"
                and (request.user.is_superuser or role in UNLOCK_ROLES)
            ),
            "verification_enabled": True,
            "total_students": len(students),
            "entered": entered,
            "missing": max(len(students) - entered, 0),
            "submission_errors": gate_errors,
            "grading_bands": [
                {
                    "min_score": float(row.min_score),
                    "max_score": float(row.max_score),
                    "grade": row.grade,
                    "points": float(row.points),
                }
                for row in GradingSystem.objects.order_by("min_score")
            ],
            "rows": rows,
        })

    def post(self, request, assessment_id: int):
        try:
            assessment, denial = self._assessment(request, assessment_id)
        except Assessment.DoesNotExist:
            return Response({"detail": "Assessment not found."}, status=status.HTTP_404_NOT_FOUND)
        if denial:
            return Response({"detail": denial}, status=status.HTTP_403_FORBIDDEN)

        students = _students_for_assessment(assessment)
        batch = ensure_batch_for_assessment(assessment)
        action = str(request.data.get("action") or "save_draft")

        if action == "unlock":
            role = _active_role(request)
            if not (request.user.is_superuser or role in UNLOCK_ROLES):
                return Response({"detail": "Your current role cannot unlock a verified batch."}, status=status.HTTP_403_FORBIDDEN)
            if batch.status != "VERIFIED":
                return Response({"detail": "Only verified batches can be unlocked."}, status=status.HTTP_409_CONFLICT)
            reset_batch_to_draft(batch, request.user)
            return Response({"detail": "Batch unlocked and reset to Draft.", "status": "DRAFT"})

        if action == "submit":
            gate_errors = _submission_gate_errors(assessment, students)
            if gate_errors:
                return Response({"detail": gate_errors[0], "errors": gate_errors}, status=status.HTTP_400_BAD_REQUEST)
            submitted_batch, sample_count, ok = submit_batch_for_verification(assessment, request.user)
            if not ok:
                return Response({"detail": "Batch already submitted or there are no results to submit."}, status=status.HTTP_409_CONFLICT)
            return Response({
                "detail": (
                    "Marks submitted and released directly to reports."
                    if submitted_batch.status == "VERIFIED"
                    else f"Batch submitted for verification. {sample_count} samples selected."
                ),
                "status": submitted_batch.status,
                "sample_count": sample_count,
            })

        if action != "save_draft":
            return Response({"detail": "Choose a valid marks action."}, status=status.HTTP_400_BAD_REQUEST)
        if batch.status not in {"DRAFT", "FLAGGED"}:
            return Response({"detail": "Results are locked after submission for verification."}, status=status.HTTP_409_CONFLICT)

        raw_rows = request.data.get("rows")
        if not isinstance(raw_rows, list):
            return Response({"detail": "Marks must be supplied as a list of student rows."}, status=status.HTTP_400_BAD_REQUEST)

        registered = {student.pk: student for student in students}
        was_flagged = batch.status == "FLAGGED"
        if was_flagged:
            batch.status = "DRAFT"
            batch.rejection_reason = None
            batch.save(update_fields=["status", "rejection_reason"])
            Result.objects.filter(batch=batch).update(status="DRAFT")

        existing = Result.objects.filter(
            assessment=assessment,
            student__is_active=True,
        ).select_related("student")
        result_by_student = {row.student_id: row for row in existing}
        validated: dict[int, dict] = {}

        for row in raw_rows:
            if not isinstance(row, dict):
                return Response({"detail": "Each marks row must contain a student and score."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                student_id = int(row.get("student_id"))
            except (TypeError, ValueError):
                return Response({"detail": "Marks contain an invalid student identifier."}, status=status.HTTP_400_BAD_REQUEST)
            student = registered.get(student_id)
            if not student:
                return Response({"detail": "Marks include a student outside this class register."}, status=status.HTTP_400_BAD_REQUEST)
            raw_score = str(row.get("score") or "").strip()
            reason = str(row.get("reason") or "").strip()
            if not raw_score:
                continue
            try:
                score = _parse_score_or_raise(raw_score, assessment, str(student))
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            current = result_by_student.get(student_id)
            score_changed = bool(current and current.score != score)
            if was_flagged and score_changed and not reason:
                return Response({
                    "detail": f"Provide a correction reason for {student} before saving flagged corrections."
                }, status=status.HTTP_400_BAD_REQUEST)
            validated[student_id] = {"score": score, "reason": reason}

        created_results = []
        updated_count = 0
        correction_count = 0
        try:
            with transaction.atomic():
                for student_id, row_data in validated.items():
                    student = registered[student_id]
                    score = row_data["score"]
                    reason = row_data["reason"]
                    current = result_by_student.get(student_id)
                    if current:
                        score_changed = current.score != score
                        if score_changed or current.status != "DRAFT" or current.batch_id != batch.pk:
                            old_score = current.score
                            current.score = score
                            current.status = "DRAFT"
                            current.batch = batch
                            current.save(update_fields=["score", "status", "batch"])
                            updated_count += 1
                            if was_flagged and score_changed:
                                record_correction(
                                    batch=batch,
                                    result=current,
                                    old_mark=old_score,
                                    new_mark=score,
                                    reason=reason,
                                    user=request.user,
                                )
                                VerificationDiscrepancy.objects.filter(batch=batch, result=current).update(
                                    corrected_mark=score,
                                    action_taken=f"Corrected by {request.user.username}",
                                )
                                correction_count += 1
                    else:
                        created_results.append(Result(
                            assessment=assessment,
                            student=student,
                            score=score,
                            batch=batch,
                            status="DRAFT",
                        ))
                if created_results:
                    Result.objects.bulk_create(created_results)
        except IntegrityError:
            return Response({
                "detail": "Could not save draft. Duplicate result rows were detected for one or more students."
            }, status=status.HTTP_409_CONFLICT)

        submitted = False
        sample_count = 0
        if bool(request.data.get("submit_after_save")):
            gate_errors = _submission_gate_errors(assessment, students)
            if gate_errors:
                return Response({
                    "detail": "Draft saved, but the batch is not ready for submission.",
                    "errors": gate_errors,
                    "created": len(created_results),
                    "updated": updated_count,
                    "corrections": correction_count,
                }, status=status.HTTP_200_OK)
            submitted_batch, sample_count, ok = submit_batch_for_verification(assessment, request.user)
            submitted = bool(ok)
            if ok:
                batch = submitted_batch

        total_results = Result.objects.filter(
            assessment=assessment,
            student__is_active=True,
        ).values("student_id").distinct().count()
        return Response({
            "detail": (
                f"Draft saved. Created {len(created_results)} and updated {updated_count} result(s)."
                if not submitted
                else f"Marks saved and submitted. {sample_count} verification samples selected."
            ),
            "created": len(created_results),
            "updated": updated_count,
            "corrections": correction_count,
            "entered": total_results,
            "missing": max(len(students) - total_results, 0),
            "status": batch.status,
            "submitted": submitted,
            "saved_at": timezone.now().isoformat(),
        })
