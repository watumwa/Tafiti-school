from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from app.models import (
    AcademicClass,
    AcademicClassStream,
    AdmissionApplication,
    AdmissionRequirement,
    ClassRegister,
    ClassSubjectAllocation,
    FeeRefund,
    OutboundDelivery,
    OutboundMessage,
    Payment,
    PaymentReversal,
    ReportCycleRemark,
    ResultBatch,
    ResultPublication,
    Staff,
    StaffContract,
    StaffLeave,
    StaffPerformanceNote,
    StaffSalaryHistory,
    Student,
    StudentAccountEntry,
    StudentLifecycleEvent,
    StudentNote,
    Stream,
)
from app.services.admissions import ensure_admission_requirements

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context


ADMIN_ROLES = {"Admin", "Head Teacher"}
STUDENT_WRITE_ROLES = {"Admin", "Head Teacher", "Admissions Officer"}
HR_WRITE_ROLES = {"Admin", "Head Teacher"}
FINANCE_WRITE_ROLES = {"Admin", "Bursar"}
RESULT_WRITE_ROLES = {"Admin", "Head Teacher", "Director of Studies"}
COMMUNICATION_WRITE_ROLES = {"Admin", "Head Teacher", "Admissions Officer"}


def _role(request):
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _allowed(request, roles):
    return bool(request.user.is_superuser or _role(request) in roles)


def _money(value):
    return f"{Decimal(value or 0):.2f}"


def _decimal(value, name="Amount"):
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{name} must be a valid number.")
    if amount <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return amount


def _student_payload(student, request):
    placements = ClassRegister.objects.filter(student=student).select_related(
        "academic_class_stream__academic_class__Class",
        "academic_class_stream__academic_class__academic_year",
        "academic_class_stream__academic_class__term",
        "academic_class_stream__stream",
    ).order_by("-academic_class_stream__academic_class__academic_year_id", "-id")
    admissions = AdmissionApplication.objects.filter(enrolled_student=student).select_related("cycle").order_by("-created_at")
    lifecycle = student.lifecycle_events.select_related("from_class", "to_class", "from_stream", "to_stream", "recorded_by")[:100]
    notes = student.profile_notes.select_related("created_by")[:100]
    documents = student.documents.order_by("-uploaded_at")[:100]
    results = student.results.select_related("assessment__subject", "assessment__assessment_type").order_by("-assessment__date")[:100]
    attendance = student.attendance_records.select_related("session__subject").order_by("-session__date")[:100]
    parent_access = student.parent_accesses.select_related("user").order_by("-verified_at")

    finance = []
    can_view_finance = _allowed(request, {"Admin", "Head Teacher", "Bursar"})
    if can_view_finance:
        for bill in student.bills.select_related("academic_class__Class", "academic_class__term").prefetch_related("payments"):
            finance.append({
                "bill_id": bill.pk,
                "class": str(bill.academic_class.Class),
                "term": str(bill.academic_class.term),
                "billed": _money(bill.total_amount),
                "paid": _money(bill.amount_paid),
                "balance": _money(bill.balance),
                "payments": [
                    {
                        "id": p.pk,
                        "date": p.payment_date.isoformat(),
                        "amount": _money(p.amount),
                        "method": p.payment_method,
                        "reference": p.reference_no,
                        "reversed": hasattr(p, "reversal"),
                    }
                    for p in bill.payments.order_by("-payment_date", "-id")
                ],
            })

    latest_event = student.lifecycle_events.first()
    lifecycle_status = latest_event.get_status_display() if latest_event else ("Active" if student.is_active else "Inactive")
    return {
        "student": {
            "id": student.pk,
            "number": student.display_student_id,
            "name": student.student_name,
            "photo": student.photo.url if student.photo else "",
            "gender": student.get_gender_display(),
            "birthdate": student.birthdate.isoformat(),
            "address": student.address,
            "guardian": student.guardian,
            "relationship": student.relationship,
            "contact": student.contact,
            "class": str(student.current_class),
            "stream": str(student.stream),
            "term": str(student.term),
            "academic_year": str(student.academic_year),
            "status": lifecycle_status,
            "is_active": student.is_active,
        },
        "admissions": [
            {"id": row.pk, "reference": row.reference, "cycle": row.cycle.name, "status": row.get_status_display(), "created_at": row.created_at.isoformat()}
            for row in admissions
        ],
        "placements": [
            {
                "class": str(row.academic_class_stream.academic_class.Class),
                "stream": str(row.academic_class_stream.stream),
                "term": str(row.academic_class_stream.academic_class.term),
                "year": str(row.academic_class_stream.academic_class.academic_year),
            }
            for row in placements
        ],
        "lifecycle": [
            {
                "id": row.pk,
                "status": row.get_status_display(),
                "date": row.effective_date.isoformat(),
                "from_class": str(row.from_class or ""),
                "to_class": str(row.to_class or ""),
                "from_stream": str(row.from_stream or ""),
                "to_stream": str(row.to_stream or ""),
                "reason": row.reason,
                "recorded_by": row.recorded_by.get_username() if row.recorded_by else "System",
            }
            for row in lifecycle
        ],
        "notes": [
            {"id": row.pk, "category": row.get_category_display(), "note": row.note, "private": row.is_private, "created_at": row.created_at.isoformat(), "by": row.created_by.get_username() if row.created_by else "System"}
            for row in notes
        ],
        "documents": [
            {"id": row.pk, "type": row.get_document_type_display(), "url": row.file.url if row.file else "", "uploaded_at": row.uploaded_at.isoformat()}
            for row in documents
        ],
        "results": [
            {"date": row.assessment.date.isoformat(), "subject": row.assessment.subject.name, "assessment": row.assessment.assessment_type.name, "score": str(row.score), "grade": row.grade, "status": row.status}
            for row in results
        ],
        "attendance": [
            {"date": row.session.date.isoformat(), "subject": str(row.session.subject), "status": row.status, "remarks": row.remarks}
            for row in attendance
        ],
        "parents": [
            {"id": row.pk, "username": row.user.username, "verified": row.is_verified, "active": row.is_active, "must_setup_password": row.must_change_password}
            for row in parent_access
        ],
        "finance": finance,
        "can_edit_lifecycle": _allowed(request, STUDENT_WRITE_ROLES),
        "can_view_finance": can_view_finance,
    }


def _staff_payload(staff):
    account = getattr(staff, "staff_account", None)
    assignments = ClassSubjectAllocation.objects.filter(subject_teacher=staff).select_related(
        "academic_class_stream__academic_class__Class", "academic_class_stream__stream", "subject"
    ).order_by("academic_class_stream__academic_class__Class__name", "subject__name")
    return {
        "staff": {
            "id": staff.pk,
            "name": str(staff),
            "department": staff.get_department_display(),
            "qualification": staff.qualification,
            "status": staff.get_staff_status_display(),
            "hire_date": staff.hire_date.isoformat(),
            "salary": _money(staff.salary),
            "roles": list(staff.roles.values_list("name", flat=True)),
            "account": {"username": account.user.username, "active": account.user.is_active} if account else None,
        },
        "contracts": [
            {"id": row.pk, "type": row.contract_type, "start": row.start_date.isoformat(), "end": row.end_date.isoformat() if row.end_date else "", "active": row.is_active, "document": row.document.url if row.document else "", "notes": row.notes}
            for row in staff.contracts.all()
        ],
        "documents": [
            {"id": row.pk, "type": row.get_document_type_display(), "url": row.file.url if row.file else "", "uploaded": row.uploaded_at.isoformat()}
            for row in staff.documents.all()
        ],
        "leave": [
            {"id": row.pk, "type": row.leave_type, "start": row.start_date.isoformat(), "end": row.end_date.isoformat(), "status": row.get_status_display(), "reason": row.reason}
            for row in staff.leave_requests.all()
        ],
        "salary_history": [
            {"id": row.pk, "amount": _money(row.amount), "effective_from": row.effective_from.isoformat(), "reason": row.reason}
            for row in staff.salary_history.all()
        ],
        "assignments": [
            {"class": str(row.academic_class_stream.academic_class.Class), "stream": str(row.academic_class_stream.stream), "subject": row.subject.name, "active": row.is_active}
            for row in assignments
        ],
        "performance": [
            {"id": row.pk, "title": row.title, "note": row.note, "rating": row.rating, "date": row.review_date.isoformat()}
            for row in staff.performance_notes.all()
        ],
    }


class CompletionWorkspaceAPIView(WorkspaceBaseAPIView):
    def get(self, request, area: str, pk: int | None = None):
        if area == "student" and pk:
            try:
                student = Student.objects.select_related("current_class", "stream", "term", "academic_year").get(pk=pk)
            except Student.DoesNotExist:
                return Response({"detail": "Student not found."}, status=status.HTTP_404_NOT_FOUND)
            return Response(_student_payload(student, request))

        if area == "staff" and pk:
            if not _allowed(request, {"Admin", "Head Teacher", "Director of Studies"}):
                return Response({"detail": "Your role cannot access the full staff workspace."}, status=status.HTTP_403_FORBIDDEN)
            try:
                staff = Staff.objects.prefetch_related("roles", "documents", "contracts", "leave_requests", "salary_history", "performance_notes").get(pk=pk)
            except Staff.DoesNotExist:
                return Response({"detail": "Staff member not found."}, status=status.HTTP_404_NOT_FOUND)
            return Response(_staff_payload(staff))

        if area == "admission" and pk:
            try:
                application = AdmissionApplication.objects.select_related("cycle", "enrolled_student").get(pk=pk)
            except AdmissionApplication.DoesNotExist:
                return Response({"detail": "Admission application not found."}, status=status.HTTP_404_NOT_FOUND)
            requirements = ensure_admission_requirements(application)
            return Response({
                "id": application.pk,
                "reference": application.reference,
                "status": application.get_status_display(),
                "student": application.student_name,
                "requirements_complete": not requirements.filter(is_required=True, is_completed=False).exists(),
                "requirements": [
                    {"id": row.pk, "name": row.name, "required": row.is_required, "completed": row.is_completed, "completed_at": row.completed_at.isoformat() if row.completed_at else "", "notes": row.notes}
                    for row in requirements
                ],
                "history": [
                    {"from": row.from_status, "to": row.to_status, "notes": row.notes, "when": row.changed_at.isoformat(), "by": row.changed_by.get_username() if row.changed_by else "System"}
                    for row in application.status_history.select_related("changed_by").all()
                ],
                "enrolled_student_id": application.enrolled_student_id,
            })

        if area == "finance" and pk:
            if not _allowed(request, {"Admin", "Head Teacher", "Bursar"}):
                return Response({"detail": "Your role cannot access financial controls."}, status=status.HTTP_403_FORBIDDEN)
            payment_rows = Payment.objects.filter(bill_id=pk).select_related("bill__student").order_by("-payment_date", "-id")
            return Response({
                "payments": [
                    {"id": row.pk, "amount": _money(row.amount), "date": row.payment_date.isoformat(), "method": row.payment_method, "reference": row.reference_no, "reversed": hasattr(row, "reversal")}
                    for row in payment_rows
                ],
                "refunds": [
                    {"id": row.pk, "payment_id": row.payment_id, "amount": _money(row.amount), "status": row.get_status_display(), "reason": row.reason, "requested_at": row.requested_at.isoformat()}
                    for row in FeeRefund.objects.filter(payment__bill_id=pk).order_by("-requested_at")
                ],
                "ledger_entries": [
                    {"id": row.pk, "type": row.get_entry_type_display(), "amount": _money(row.amount), "reference": row.reference, "notes": row.notes, "created_at": row.created_at.isoformat()}
                    for row in StudentAccountEntry.objects.filter(bill_id=pk)
                ],
            })

        if area == "results" and pk:
            try:
                academic_class = AcademicClass.objects.select_related("Class", "academic_year", "term").get(pk=pk)
            except AcademicClass.DoesNotExist:
                return Response({"detail": "Academic class not found."}, status=status.HTTP_404_NOT_FOUND)
            publication, _ = ResultPublication.objects.get_or_create(academic_class=academic_class)
            batches = ResultBatch.objects.filter(assessment__academic_class=academic_class)
            return Response({
                "class_id": academic_class.pk,
                "class": str(academic_class.Class),
                "term": str(academic_class.term),
                "year": str(academic_class.academic_year),
                "assessment_batches": batches.count(),
                "verified_batches": batches.filter(status="VERIFIED").count(),
                "all_verified": bool(batches.exists() and not batches.exclude(status="VERIFIED").exists()),
                "locked": publication.is_locked,
                "published": publication.is_published,
                "locked_at": publication.locked_at.isoformat() if publication.locked_at else "",
                "published_at": publication.published_at.isoformat() if publication.published_at else "",
            })

        if area == "outbound":
            if not _allowed(request, COMMUNICATION_WRITE_ROLES):
                return Response({"detail": "Your role cannot access outbound communications."}, status=status.HTTP_403_FORBIDDEN)
            messages = OutboundMessage.objects.prefetch_related("deliveries")[:200]
            return Response({"messages": [
                {"id": row.pk, "channel": row.channel, "subject": row.subject, "audience": row.audience_label, "recipients": row.recipient_count, "status": row.get_status_display(), "sent": row.deliveries.filter(status__in=("sent", "delivered")).count(), "failed": row.deliveries.filter(status="failed").count(), "cost": _money(row.actual_cost), "created_at": row.created_at.isoformat()}
                for row in messages
            ]})

        return Response({"detail": "Unknown completion workspace."}, status=status.HTTP_404_NOT_FOUND)

    @transaction.atomic
    def post(self, request, area: str, pk: int | None = None):
        action = str(request.data.get("action") or "").strip().lower()

        if area == "student" and pk:
            if not _allowed(request, STUDENT_WRITE_ROLES):
                return Response({"detail": "Your role cannot change the student lifecycle."}, status=status.HTTP_403_FORBIDDEN)
            try:
                student = Student.objects.select_for_update().get(pk=pk)
            except Student.DoesNotExist:
                return Response({"detail": "Student not found."}, status=status.HTTP_404_NOT_FOUND)

            if action == "add_note":
                text = str(request.data.get("note") or "").strip()
                if not text:
                    return Response({"detail": "A note is required."}, status=status.HTTP_400_BAD_REQUEST)
                row = StudentNote.objects.create(student=student, category=str(request.data.get("category") or "general"), note=text, is_private=bool(request.data.get("is_private", True)), created_by=request.user)
                return Response({"detail": "Student note added.", "id": row.pk}, status=status.HTTP_201_CREATED)

            if action == "change_status":
                new_status = str(request.data.get("status") or "").strip().lower()
                valid = {value for value, _ in StudentLifecycleEvent.STATUS_CHOICES}
                if new_status not in valid:
                    return Response({"detail": "Select a valid lifecycle status."}, status=status.HTTP_400_BAD_REQUEST)
                active_statuses = {StudentLifecycleEvent.STATUS_ACTIVE, StudentLifecycleEvent.STATUS_REACTIVATED}
                student.is_active = new_status in active_statuses
                student.save(update_fields=("is_active",))
                event = StudentLifecycleEvent.objects.create(student=student, status=new_status, reason=str(request.data.get("reason") or ""), effective_date=request.data.get("effective_date") or timezone.localdate(), from_class=student.current_class, from_stream=student.stream, recorded_by=request.user)
                return Response({"detail": "Student lifecycle status updated.", "id": event.pk})

            if action == "transfer":
                academic_class_id = request.data.get("academic_class_id")
                stream_id = request.data.get("stream_id")
                try:
                    target_class = AcademicClass.objects.select_related("Class", "academic_year", "term").get(pk=academic_class_id)
                    target_stream = Stream.objects.get(pk=stream_id)
                    class_stream = AcademicClassStream.objects.get(academic_class=target_class, stream=target_stream)
                except (AcademicClass.DoesNotExist, Stream.DoesNotExist, AcademicClassStream.DoesNotExist):
                    return Response({"detail": "The target class and stream combination is not configured."}, status=status.HTTP_400_BAD_REQUEST)
                old_class, old_stream = student.current_class, student.stream
                ClassRegister.objects.get_or_create(academic_class_stream=class_stream, student=student)
                student.current_class = target_class.Class
                student.stream = target_stream
                student.term = target_class.term
                student.academic_year = target_class.academic_year
                student.is_active = True
                student.save(update_fields=("current_class", "stream", "term", "academic_year", "is_active"))
                event = StudentLifecycleEvent.objects.create(student=student, status=StudentLifecycleEvent.STATUS_TRANSFERRED, reason=str(request.data.get("reason") or "Student transferred."), from_class=old_class, to_class=student.current_class, from_stream=old_stream, to_stream=student.stream, effective_date=request.data.get("effective_date") or timezone.localdate(), recorded_by=request.user)
                return Response({"detail": "Student transferred and placement history retained.", "id": event.pk})

        if area == "staff" and pk:
            if not _allowed(request, HR_WRITE_ROLES):
                return Response({"detail": "Your role cannot change HR records."}, status=status.HTTP_403_FORBIDDEN)
            try:
                staff = Staff.objects.get(pk=pk)
            except Staff.DoesNotExist:
                return Response({"detail": "Staff member not found."}, status=status.HTTP_404_NOT_FOUND)
            if action == "contract":
                row = StaffContract(staff=staff, contract_type=str(request.data.get("contract_type") or "Employment"), start_date=request.data.get("start_date"), end_date=request.data.get("end_date") or None, notes=str(request.data.get("notes") or ""), created_by=request.user)
                row.full_clean(); row.save()
                return Response({"detail": "Contract recorded.", "id": row.pk}, status=status.HTTP_201_CREATED)
            if action == "leave":
                row = StaffLeave(staff=staff, leave_type=str(request.data.get("leave_type") or "Annual"), start_date=request.data.get("start_date"), end_date=request.data.get("end_date"), reason=str(request.data.get("reason") or ""))
                row.full_clean(); row.save()
                return Response({"detail": "Leave request recorded.", "id": row.pk}, status=status.HTTP_201_CREATED)
            if action == "leave_decision":
                try:
                    row = staff.leave_requests.get(pk=request.data.get("leave_id"))
                except StaffLeave.DoesNotExist:
                    return Response({"detail": "Leave request not found."}, status=status.HTTP_404_NOT_FOUND)
                decision = str(request.data.get("status") or "").lower()
                if decision not in {StaffLeave.STATUS_APPROVED, StaffLeave.STATUS_REJECTED, StaffLeave.STATUS_CANCELLED}:
                    return Response({"detail": "Invalid leave decision."}, status=status.HTTP_400_BAD_REQUEST)
                row.status = decision; row.decided_by = request.user; row.decided_at = timezone.now(); row.save(update_fields=("status", "decided_by", "decided_at"))
                return Response({"detail": "Leave decision recorded."})
            if action == "salary":
                try:
                    amount = _decimal(request.data.get("amount"))
                except ValueError as exc:
                    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
                row = StaffSalaryHistory.objects.create(staff=staff, amount=amount, effective_from=request.data.get("effective_from") or timezone.localdate(), reason=str(request.data.get("reason") or ""), recorded_by=request.user)
                staff.salary = amount; staff.save(update_fields=("salary",))
                return Response({"detail": "Salary history updated.", "id": row.pk})
            if action == "performance":
                row = StaffPerformanceNote(staff=staff, title=str(request.data.get("title") or "Performance review"), note=str(request.data.get("note") or ""), rating=request.data.get("rating") or None, review_date=request.data.get("review_date") or timezone.localdate(), created_by=request.user)
                row.full_clean(); row.save()
                return Response({"detail": "Performance note recorded.", "id": row.pk}, status=status.HTTP_201_CREATED)

        if area == "admission" and pk:
            if not _allowed(request, STUDENT_WRITE_ROLES):
                return Response({"detail": "Your role cannot manage admission requirements."}, status=status.HTTP_403_FORBIDDEN)
            try:
                application = AdmissionApplication.objects.get(pk=pk)
            except AdmissionApplication.DoesNotExist:
                return Response({"detail": "Admission application not found."}, status=status.HTTP_404_NOT_FOUND)
            ensure_admission_requirements(application)
            if action == "requirement":
                try:
                    row = application.requirements.get(pk=request.data.get("requirement_id"))
                except AdmissionRequirement.DoesNotExist:
                    return Response({"detail": "Admission requirement not found."}, status=status.HTTP_404_NOT_FOUND)
                completed = bool(request.data.get("completed"))
                row.is_completed = completed
                row.completed_at = timezone.now() if completed else None
                row.completed_by = request.user if completed else None
                row.notes = str(request.data.get("notes") or row.notes)
                row.save(update_fields=("is_completed", "completed_at", "completed_by", "notes"))
                return Response({"detail": "Admission requirement updated."})
            if action == "add_requirement":
                name = str(request.data.get("name") or "").strip()
                if not name:
                    return Response({"detail": "Requirement name is required."}, status=status.HTTP_400_BAD_REQUEST)
                row, created = AdmissionRequirement.objects.get_or_create(application=application, name=name, defaults={"is_required": bool(request.data.get("required", True))})
                return Response({"detail": "Admission requirement added." if created else "Requirement already exists.", "id": row.pk})

        if area == "finance" and pk:
            if not _allowed(request, FINANCE_WRITE_ROLES):
                return Response({"detail": "Your role cannot perform accounting actions."}, status=status.HTTP_403_FORBIDDEN)
            try:
                payment = Payment.objects.select_for_update().select_related("bill__student").get(pk=pk)
            except Payment.DoesNotExist:
                return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)
            if action == "reverse_payment":
                if hasattr(payment, "reversal"):
                    return Response({"detail": "This payment has already been reversed."}, status=status.HTTP_409_CONFLICT)
                reason = str(request.data.get("reason") or "").strip()
                if not reason:
                    return Response({"detail": "A reversal reason is required."}, status=status.HTTP_400_BAD_REQUEST)
                PaymentReversal.objects.create(payment=payment, reason=reason, reversed_by=request.user)
                reference = f"REV-{payment.pk}-{uuid4().hex[:10].upper()}"
                Payment.objects.create(bill=payment.bill, payment_date=timezone.localdate(), amount=-Decimal(payment.amount), payment_method=payment.payment_method, fee_category=payment.fee_category, reference_no=reference, recorded_by=request.user.get_username(), notes=f"Reversal of {payment.reference_no}: {reason}")
                StudentAccountEntry.objects.create(student=payment.bill.student, bill=payment.bill, entry_type=StudentAccountEntry.TYPE_REVERSAL, amount=-Decimal(payment.amount), reference=reference, notes=reason, created_by=request.user)
                return Response({"detail": "Payment reversed with a compensating ledger transaction.", "reference": reference})
            if action == "refund_request":
                try:
                    amount = _decimal(request.data.get("amount"))
                except ValueError as exc:
                    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
                already = sum((row.amount for row in payment.refunds.exclude(status=FeeRefund.STATUS_REJECTED)), Decimal("0"))
                if amount + already > Decimal(payment.amount):
                    return Response({"detail": "Refunds cannot exceed the original payment."}, status=status.HTTP_400_BAD_REQUEST)
                refund = FeeRefund.objects.create(payment=payment, amount=amount, reason=str(request.data.get("reason") or ""), requested_by=request.user)
                return Response({"detail": "Refund request created for approval.", "id": refund.pk}, status=status.HTTP_201_CREATED)
            if action == "refund_decision":
                try:
                    refund = payment.refunds.select_for_update().get(pk=request.data.get("refund_id"))
                except FeeRefund.DoesNotExist:
                    return Response({"detail": "Refund request not found."}, status=status.HTTP_404_NOT_FOUND)
                decision = str(request.data.get("status") or "").lower()
                if decision not in {FeeRefund.STATUS_APPROVED, FeeRefund.STATUS_REJECTED, FeeRefund.STATUS_PAID}:
                    return Response({"detail": "Invalid refund decision."}, status=status.HTTP_400_BAD_REQUEST)
                refund.status = decision; refund.approved_by = request.user; refund.approved_at = timezone.now(); refund.save(update_fields=("status", "approved_by", "approved_at"))
                if decision == FeeRefund.STATUS_PAID and not StudentAccountEntry.objects.filter(reference=f"REFUND-{refund.pk}").exists():
                    StudentAccountEntry.objects.create(student=payment.bill.student, bill=payment.bill, entry_type=StudentAccountEntry.TYPE_REFUND, amount=-refund.amount, reference=f"REFUND-{refund.pk}", notes=refund.reason, created_by=request.user)
                return Response({"detail": "Refund decision recorded."})

        if area == "results" and pk:
            if not _allowed(request, RESULT_WRITE_ROLES):
                return Response({"detail": "Your role cannot publish results."}, status=status.HTTP_403_FORBIDDEN)
            try:
                academic_class = AcademicClass.objects.get(pk=pk)
            except AcademicClass.DoesNotExist:
                return Response({"detail": "Academic class not found."}, status=status.HTTP_404_NOT_FOUND)
            publication, _ = ResultPublication.objects.select_for_update().get_or_create(academic_class=academic_class)
            batches = ResultBatch.objects.filter(assessment__academic_class=academic_class)
            if action in {"lock", "publish"} and (not batches.exists() or batches.exclude(status="VERIFIED").exists()):
                return Response({"detail": "All assessment batches must be verified before locking or publishing."}, status=status.HTTP_409_CONFLICT)
            if action == "lock":
                publication.is_locked = True; publication.locked_at = timezone.now(); publication.locked_by = request.user
                publication.save(update_fields=("is_locked", "locked_at", "locked_by"))
                return Response({"detail": "Result set locked."})
            if action == "publish":
                if not publication.is_locked:
                    publication.is_locked = True; publication.locked_at = timezone.now(); publication.locked_by = request.user
                publication.is_published = True; publication.published_at = timezone.now(); publication.published_by = request.user
                publication.save()
                return Response({"detail": "Results published to the parent-facing reporting layer."})
            if action == "unpublish":
                if not _allowed(request, ADMIN_ROLES):
                    return Response({"detail": "Only school leadership can unpublish results."}, status=status.HTTP_403_FORBIDDEN)
                publication.is_published = False; publication.published_at = None; publication.published_by = None; publication.save(update_fields=("is_published", "published_at", "published_by"))
                return Response({"detail": "Results unpublished. Audit the reason separately before republishing."})

        if area == "outbound":
            if not _allowed(request, COMMUNICATION_WRITE_ROLES):
                return Response({"detail": "Your role cannot queue outbound communications."}, status=status.HTTP_403_FORBIDDEN)
            if action == "queue":
                channel = str(request.data.get("channel") or "sms").lower()
                if channel not in {"sms", "email", "both"}:
                    return Response({"detail": "Invalid communication channel."}, status=status.HTTP_400_BAD_REQUEST)
                recipients = request.data.get("recipients") or []
                if not isinstance(recipients, list) or not recipients:
                    return Response({"detail": "At least one recipient is required."}, status=status.HTTP_400_BAD_REQUEST)
                message = OutboundMessage.objects.create(channel=channel, subject=str(request.data.get("subject") or ""), body=str(request.data.get("body") or ""), audience_label=str(request.data.get("audience") or "Custom recipients"), recipient_count=len(recipients), created_by=request.user)
                deliveries = []
                for recipient in recipients:
                    name = str(recipient.get("name") or "")
                    consented = bool(recipient.get("consented", True))
                    if channel in {"sms", "both"} and recipient.get("phone"):
                        deliveries.append(OutboundDelivery(message=message, recipient_name=name, destination=str(recipient["phone"]), channel="sms", consented=consented, status="queued" if consented else "skipped"))
                    if channel in {"email", "both"} and recipient.get("email"):
                        deliveries.append(OutboundDelivery(message=message, recipient_name=name, destination=str(recipient["email"]), channel="email", consented=consented, status="queued" if consented else "skipped"))
                OutboundDelivery.objects.bulk_create(deliveries)
                message.recipient_count = len(deliveries); message.save(update_fields=("recipient_count",))
                return Response({"detail": "Message queued for delivery.", "id": message.pk, "deliveries": len(deliveries)}, status=status.HTTP_201_CREATED)

        return Response({"detail": "Unknown completion workflow action."}, status=status.HTTP_400_BAD_REQUEST)
