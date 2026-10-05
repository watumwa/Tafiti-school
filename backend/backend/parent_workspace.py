import base64
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import get_authorization_header
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from app.models import (
    AttendanceRecord,
    Event,
    Message,
    ParentAccess,
    ParentConversation,
    ParentNotification,
    ParentPortalAudit,
    Payment,
    Result,
    StudentBill,
    Term,
)
from app.services.parent_experience import current_academic_term, subject_performance, verified_results_for
from app.services.parent_portal import (
    ParentAccessError,
    eligible_parent_teachers,
    start_parent_conversation,
    sync_parent_notifications,
)
from app.utils.pdf_utils import generate_student_report_pdf
from .auth import canonical_role_label, resolve_active_role


class ParentWorkspaceAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _accesses(self, request):
        return ParentAccess.objects.filter(
            user=request.user,
            is_active=True,
            is_verified=True,
            student__is_active=True,
        ).select_related("student", "student__current_class", "student__stream")

    def _is_parent(self, request):
        if not getattr(settings, "PARENT_PORTAL_ENABLED", True):
            return False
        auth = getattr(request, "auth", None)
        try:
            context = auth.get("portal_context") if auth else None
        except AttributeError:
            context = None
        return canonical_role_label(resolve_active_role(request.user, context).label) == "Parent"

    def _audit(self, request, *, student=None, details, action=ParentPortalAudit.ACTION_VIEWED):
        ip = request.META.get("REMOTE_ADDR")
        ParentPortalAudit.objects.create(
            user=request.user,
            student=student,
            action=action,
            ip_address=ip if ip else None,
            details=details,
        )

    def _denied(self):
        return Response(
            {"detail": "This parent workspace is not available to the current account."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def get(self, request, action: str):
        if not self._is_parent(request):
            return self._denied()

        accesses = list(self._accesses(request))
        if not accesses:
            return self._denied()
        access_by_id = {row.student_id: row for row in accesses}

        if action == "profile":
            user = request.user
            self._audit(request, details={"page": "profile"})
            return Response({
                "profile": {
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "username": user.get_username(),
                },
                "children": [
                    {
                        "id": row.student_id,
                        "name": row.student.student_name,
                        "student_id": row.student.display_student_id,
                        "class": str(row.student.current_class),
                        "stream": str(row.student.stream),
                        "photo": row.student.photo.url if row.student.photo else "",
                        "can_view_academics": row.can_view_academics,
                        "can_view_finance": row.can_view_finance,
                        "can_view_attendance": row.can_view_attendance,
                    }
                    for row in accesses
                ],
            })

        if action == "children":
            from app.services.parent_experience import child_summary

            term = current_academic_term()
            self._audit(request, details={"page": "children"})
            return Response({
                "term": str(term) if term else "",
                "children": [
                    self._child_summary(child_summary(row, term), row)
                    for row in accesses
                ],
            })

        if action == "attendance":
            selected_student = request.query_params.get("student", "")
            permitted = [
                access for access in accesses
                if access.can_view_attendance
                and (not selected_student or str(access.student_id) == selected_student)
            ]
            student_ids = [access.student_id for access in permitted]
            records = AttendanceRecord.objects.filter(
                student_id__in=student_ids,
                session__is_locked=True,
            ).select_related(
                "student", "session__class_stream", "session__subject",
            ).order_by("-session__date", "-session_id")[:500]
            totals = {"present": 0, "absent": 0, "late": 0, "excused": 0}
            rows = []
            for record in records:
                status_key = record.status.lower()
                if status_key in totals:
                    totals[status_key] += 1
                rows.append({
                    "id": record.pk,
                    "student_id": record.student_id,
                    "student": record.student.student_name,
                    "date": record.session.date.isoformat(),
                    "class": str(record.session.class_stream),
                    "subject": str(record.session.subject),
                    "status": record.get_status_display(),
                    "remarks": record.remarks,
                })
            self._audit(
                request,
                student=permitted[0].student if len(permitted) == 1 else None,
                details={"page": "attendance"},
            )
            return Response({
                "students": [
                    {"id": access.student_id, "name": access.student.student_name}
                    for access in accesses if access.can_view_attendance
                ],
                "totals": totals,
                "records": rows,
            })

        if action == "finance":
            selected_student = request.query_params.get("student", "")
            permitted = [
                access for access in accesses
                if access.can_view_finance
                and (not selected_student or str(access.student_id) == selected_student)
            ]
            student_ids = [access.student_id for access in permitted]
            bills = list(StudentBill.objects.filter(
                student_id__in=student_ids,
            ).select_related(
                "student", "academic_class__term",
            ).prefetch_related(
                "items", "payments", "applied_credits",
            ).order_by("-bill_date", "-id")[:500])
            bill_rows = []
            for bill in bills:
                balance = Decimal(str(bill.balance))
                paid = Decimal(str(bill.amount_paid))
                bill_rows.append({
                    "id": bill.pk,
                    "student_id": bill.student_id,
                    "student": bill.student.student_name,
                    "term": str(bill.academic_class.term),
                    "date": bill.bill_date.isoformat(),
                    "due_date": bill.due_date.isoformat() if bill.due_date else "",
                    "billed": f"{Decimal(str(bill.total_amount)):.2f}",
                    "paid": f"{paid:.2f}",
                    "balance": f"{balance:.2f}",
                    "status": "Paid" if balance <= 0 else ("Partial" if paid > 0 else "Outstanding"),
                    "items": [
                        {"description": item.description, "amount": f"{item.amount:.2f}"}
                        for item in bill.items.all()
                    ],
                })
            payments = Payment.objects.filter(
                bill_id__in=[bill.pk for bill in bills],
            ).select_related("bill__student").order_by("-payment_date", "-id")[:500]
            payment_rows = [
                {
                    "id": payment.pk,
                    "student_id": payment.bill.student_id,
                    "student": payment.bill.student.student_name,
                    "date": payment.payment_date.isoformat(),
                    "amount": f"{payment.amount:.2f}",
                    "method": payment.payment_method,
                    "reference": payment.reference_no,
                }
                for payment in payments
            ]
            self._audit(
                request,
                student=permitted[0].student if len(permitted) == 1 else None,
                details={"page": "finance"},
            )
            return Response({
                "students": [
                    {"id": access.student_id, "name": access.student.student_name}
                    for access in accesses if access.can_view_finance
                ],
                "summary": {
                    "billed": f"{sum((Decimal(row['billed']) for row in bill_rows), Decimal('0')):.2f}",
                    "paid": f"{sum((Decimal(row['paid']) for row in bill_rows), Decimal('0')):.2f}",
                    "balance": f"{sum((max(Decimal('0'), Decimal(row['balance'])) for row in bill_rows), Decimal('0')):.2f}",
                },
                "bills": bill_rows,
                "payments": payment_rows,
            })

        if action == "calendar":
            now = timezone.now()
            events = Event.objects.filter(
                is_active=True,
                audience__in=("all", "parents"),
                start_datetime__gte=now - timedelta(days=30),
                start_datetime__lte=now + timedelta(days=180),
            ).order_by("start_datetime", "title")[:200]
            self._audit(request, details={"page": "calendar"})
            return Response({
                "events": [
                    {
                        "id": event.pk,
                        "title": event.title,
                        "description": event.description,
                        "location": event.location,
                        "start": event.start_datetime.isoformat(),
                        "end": event.end_datetime.isoformat() if event.end_datetime else "",
                    }
                    for event in events
                ],
            })

        if action == "results":
            student_id = request.query_params.get("student")
            term_id = request.query_params.get("term")
            term = Term.objects.filter(pk=term_id).first() if term_id and term_id.isdigit() else current_academic_term()
            allowed = [
                access for access in accesses
                if access.can_view_academics and (
                    not student_id or str(access.student_id) == student_id
                )
            ]
            rows = []
            performance = []
            for access in allowed:
                results = verified_results_for(access.student, term).select_related(
                    "assessment__subject", "assessment__assessment_type",
                ).order_by("-assessment__date", "assessment__subject__name")
                for result in results:
                    percentage = (
                        Decimal(str(result.score)) * Decimal("100") / Decimal(result.assessment.out_of)
                        if result.assessment.out_of else Decimal("0")
                    )
                    rows.append({
                        "id": result.pk,
                        "student_id": access.student_id,
                        "student": access.student.student_name,
                        "subject": result.assessment.subject.name,
                        "assessment": result.assessment.assessment_type.name,
                        "date": result.assessment.date.isoformat(),
                        "score": f"{result.score:.2f}",
                        "out_of": result.assessment.out_of,
                        "percentage": round(float(percentage), 1),
                        "grade": result.grade,
                    })
                performance.extend({
                    "student_id": access.student_id,
                    "student": access.student.student_name,
                    "subject": str(row["subject"]),
                    "average": round(float(row["average"]), 1) if row["average"] is not None else None,
                    "class_average": round(float(row["class_average"]), 1) if row["class_average"] is not None else None,
                    "rank": row["rank"],
                    "class_size": row["class_size"],
                    "grade": row["grade"],
                    "assessment_count": row["assessment_count"],
                } for row in subject_performance(access.student, term))
            self._audit(
                request,
                student=allowed[0].student if len(allowed) == 1 else None,
                details={"page": "results", "term_id": term.pk if term else None},
            )
            return Response({
                "term": {"id": term.pk, "label": str(term)} if term else None,
                "terms": [
                    {"id": row.pk, "label": str(row)}
                    for row in Term.objects.select_related("academic_year").order_by("-academic_year__academic_year", "term")
                ],
                "students": [
                    {"id": row.student_id, "name": row.student.student_name}
                    for row in accesses if row.can_view_academics
                ],
                "results": rows,
                "performance": performance,
            })

        if action == "communication":
            from django.db.models import Prefetch

            conversations = ParentConversation.objects.filter(
                parent=request.user,
                student_id__in=access_by_id,
            ).select_related("student", "staff", "thread").prefetch_related(
                Prefetch("thread__messages", queryset=Message.objects.select_related("sender").order_by("created_at")),
            ).order_by("-thread__updated_at")
            teachers = {}
            for access in accesses:
                teachers[access.student_id] = [
                    {"id": staff.pk, "name": str(staff)}
                    for staff in eligible_parent_teachers(access.student)
                ]
            self._audit(request, details={"page": "communication"})
            return Response({
                "children": [
                    {"id": row.student_id, "name": row.student.student_name}
                    for row in accesses
                ],
                "teachers": teachers,
                "conversations": [
                    {
                        "id": row.pk,
                        "student_id": row.student_id,
                        "student": row.student.student_name,
                        "teacher": str(row.staff),
                        "subject": row.thread.subject or "School message",
                        "updated_at": row.thread.updated_at.isoformat(),
                        "active": row.is_active,
                        "messages": [
                            {
                                "id": message.pk,
                                "sender": message.sender.get_full_name().strip() or message.sender.get_username() if message.sender else "School",
                                "from_parent": message.sender_id == request.user.pk,
                                "body": message.body,
                                "created_at": message.created_at.isoformat(),
                            }
                            for message in row.thread.messages.all()
                        ],
                    }
                    for row in conversations
                ],
            })

        if action == "notifications":
            sync_parent_notifications(request.user)
            notifications = ParentNotification.objects.filter(
                user=request.user,
            ).filter(
                # Notifications without a student are school-wide notices.
                student__isnull=True,
            ) | ParentNotification.objects.filter(
                user=request.user,
                student_id__in=access_by_id,
            )
            self._audit(request, details={"page": "notifications"})
            return Response({
                "notifications": [
                    {
                        "id": row.pk,
                        "student": row.student.student_name if row.student_id else "",
                        "kind": row.kind,
                        "title": row.title,
                        "message": row.message,
                        "destination": row.destination,
                        "created_at": row.created_at.isoformat(),
                        "read": bool(row.read_at),
                    }
                    for row in notifications.select_related("student").order_by("-created_at")[:100]
                ],
            })

        if action == "reports":
            term = current_academic_term()
            students = [
                {"id": row.student_id, "name": row.student.student_name}
                for row in accesses if row.can_view_academics
            ]
            self._audit(request, details={"page": "reports"})
            return Response({
                "students": students,
                "terms": [
                    {"id": row.pk, "label": str(row)}
                    for row in Term.objects.select_related("academic_year").order_by("-academic_year__academic_year", "term")
                ],
                "current_term_id": term.pk if term else None,
            })

        return Response({"detail": "Unknown parent workspace action."}, status=status.HTTP_404_NOT_FOUND)

    @staticmethod
    def _child_summary(summary, access):
        student = access.student
        return {
            "id": student.pk,
            "name": student.student_name,
            "student_id": student.display_student_id,
            "photo": student.photo.url if student.photo else "",
            "class": str(student.current_class),
            "stream": str(student.stream),
            "attendance_percent": summary["attendance_percent"] if access.can_view_attendance else None,
            "academic_average": round(float(summary["academic_average"]), 1)
            if access.can_view_academics and summary["academic_average"] is not None else None,
            "outstanding_balance": f'{summary["balance"]:.2f}'
            if access.can_view_finance else None,
            "total_billed": f'{summary["total_billed"]:.2f}'
            if access.can_view_finance else None,
            "total_paid": f'{summary["total_paid"]:.2f}'
            if access.can_view_finance else None,
            "active_loans": summary["active_loan_count"],
            "overdue_loans": summary["overdue_loan_count"],
            "permissions": {
                "academics": access.can_view_academics,
                "finance": access.can_view_finance,
                "attendance": access.can_view_attendance,
            },
        }

    def patch(self, request, action: str):
        if action != "profile" or not self._is_parent(request) or not self._accesses(request).exists():
            return self._denied()

        first_name = str(request.data.get("first_name", "")).strip()
        last_name = str(request.data.get("last_name", "")).strip()
        email = str(request.data.get("email", "")).strip()
        if not first_name:
            return Response({"errors": {"first_name": ["Enter your first name."]}}, status=status.HTTP_400_BAD_REQUEST)
        if len(first_name) > 150 or len(last_name) > 150 or len(email) > 254:
            return Response({"errors": {"profile": ["One or more profile fields are too long."]}}, status=status.HTTP_400_BAD_REQUEST)
        if email:
            try:
                validate_email(email)
            except ValidationError:
                return Response({"errors": {"email": ["Enter a valid email address."]}}, status=status.HTTP_400_BAD_REQUEST)
        if email and request.user.__class__.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
            return Response({"errors": {"email": ["That email address is already in use."]}}, status=status.HTTP_400_BAD_REQUEST)

        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.email = email
        request.user.save(update_fields=("first_name", "last_name", "email"))
        self._audit(
            request,
            details={"page": "profile"},
            action="profile_updated",
        )
        return Response({"detail": "Profile updated.", "profile": {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "username": request.user.get_username(),
        }})

    def post(self, request, action: str):
        if not self._is_parent(request):
            return self._denied()
        accesses = {row.student_id: row for row in self._accesses(request)}

        if action == "message":
            student_id = request.data.get("student_id")
            teacher_id = request.data.get("teacher_id")
            subject = str(request.data.get("subject", "")).strip()
            body = str(request.data.get("message", "")).strip()
            if not str(student_id or "").isdigit() or not str(teacher_id or "").isdigit():
                return Response({"detail": "Select a linked child and assigned teacher."}, status=status.HTTP_400_BAD_REQUEST)
            access = accesses.get(int(student_id))
            if not access:
                return self._denied()
            if not body or len(body) > 2000 or len(subject) > 200:
                return Response({"detail": "Enter a message of up to 2,000 characters and a subject up to 200 characters."}, status=status.HTTP_400_BAD_REQUEST)
            from app.models import Staff

            teacher = Staff.objects.filter(pk=teacher_id, staff_status="Active").first()
            if teacher is None:
                return Response({"detail": "The selected teacher is not available."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                conversation = start_parent_conversation(
                    parent=request.user,
                    student=access.student,
                    teacher=teacher,
                    subject=subject,
                    body=body,
                )
            except ParentAccessError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            self._audit(request, student=access.student, details={"page": "communication", "action": "message_sent"})
            return Response({"detail": "Message sent.", "conversation_id": conversation.pk}, status=status.HTTP_201_CREATED)

        if action == "reply":
            conversation_id = request.data.get("conversation_id")
            body = str(request.data.get("message", "")).strip()
            conversation = ParentConversation.objects.filter(
                pk=conversation_id,
                parent=request.user,
                student_id__in=accesses,
                is_active=True,
            ).select_related("thread", "student").first()
            if conversation is None:
                return self._denied()
            if not body or len(body) > 2000:
                return Response({"detail": "Enter a message of up to 2,000 characters."}, status=status.HTTP_400_BAD_REQUEST)
            with transaction.atomic():
                Message.objects.create(thread=conversation.thread, sender=request.user, body=body)
                conversation.thread.save(update_fields=("updated_at",))
            self._audit(request, student=conversation.student, details={"page": "communication", "action": "message_replied"})
            return Response({"detail": "Reply sent."}, status=status.HTTP_201_CREATED)

        if action == "notifications-read":
            notice_id = request.data.get("notification_id")
            notices = ParentNotification.objects.filter(user=request.user).filter(
                student__isnull=True,
            ) | ParentNotification.objects.filter(user=request.user, student_id__in=accesses)
            if notice_id == "all":
                notices.filter(read_at__isnull=True).update(read_at=timezone.now())
                return Response({"detail": "All notifications marked as read."})
            if not str(notice_id or "").isdigit():
                return Response({"detail": "A notification id is required."}, status=status.HTTP_400_BAD_REQUEST)
            updated = notices.filter(pk=int(notice_id), read_at__isnull=True).update(read_at=timezone.now())
            if not updated and not notices.filter(pk=int(notice_id)).exists():
                return self._denied()
            return Response({"detail": "Notification marked as read."})

        if action == "report":
            student_id = request.data.get("student_id")
            term_id = request.data.get("term_id")
            if not str(student_id or "").isdigit():
                return Response({"detail": "Select a linked child."}, status=status.HTTP_400_BAD_REQUEST)
            access = accesses.get(int(student_id))
            if not access or not access.can_view_academics:
                return self._denied()
            results = Result.objects.filter(
                student=access.student,
                status="VERIFIED",
            ).select_related("assessment__subject", "assessment__assessment_type")
            term = Term.objects.filter(pk=term_id).first() if str(term_id or "").isdigit() else current_academic_term()
            if term:
                results = results.filter(assessment__academic_class__term=term)
            results = results.order_by("assessment__subject__name", "assessment__date")
            if not results.exists():
                return Response({"detail": "No verified results are available for this report."}, status=status.HTTP_404_NOT_FOUND)
            buffer = generate_student_report_pdf(access.student, results)
            self._audit(
                request,
                student=access.student,
                details={"page": "report_download", "term_id": term.pk if term else None},
            )
            return Response({
                "filename": f"{access.student.reg_no}-verified-results.pdf",
                "content_type": "application/pdf",
                "content_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
            })

        return Response({"detail": "Unknown parent workspace action."}, status=status.HTTP_404_NOT_FOUND)
