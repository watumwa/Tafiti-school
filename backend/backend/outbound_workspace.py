from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from app.models import CommunicationPreference, OutboundMessage, Student
from app.services.outbound_communications import send_fee_balance_reminder, send_report_ready_notice

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context


READ_ROLES = {"Admin", "Head Teacher", "Director of Studies", "Bursar", "Class Teacher"}
FEE_SEND_ROLES = {"Admin", "Head Teacher", "Bursar"}
REPORT_SEND_ROLES = {"Admin", "Head Teacher", "Director of Studies", "Class Teacher"}


def _role(request):
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can(request, roles):
    return bool(request.user.is_superuser or _role(request) in roles)


def _student_row(student):
    preference = CommunicationPreference.objects.filter(student=student).first()
    outstanding = sum((max(bill.balance, 0) for bill in student.bills.all()), 0)
    return {
        "id": student.pk,
        "student": student.student_name,
        "reg_no": student.reg_no,
        "class": str(student.current_class),
        "guardian": student.guardian,
        "guardian_phone": (preference.guardian_phone if preference else "") or student.contact,
        "guardian_email": preference.guardian_email if preference else "",
        "whatsapp_number": preference.whatsapp_number if preference else "",
        "sms_enabled": preference.sms_enabled if preference else True,
        "email_enabled": preference.email_enabled if preference else True,
        "whatsapp_enabled": preference.whatsapp_enabled if preference else False,
        "opted_out": bool(preference and preference.opted_out_at),
        "outstanding": f"{outstanding:.2f}",
    }


def _message_row(message):
    return {
        "id": message.pk,
        "student": message.student.student_name,
        "reg_no": message.student.reg_no,
        "channel": message.channel,
        "recipient": message.recipient,
        "template": message.template_key or "Custom",
        "status": message.status,
        "attempts": message.attempts,
        "created": message.created_at.isoformat(),
        "sent": message.sent_at.isoformat() if message.sent_at else "",
        "provider_response": message.provider_response,
    }


class OutboundCommunicationAPIView(WorkspaceBaseAPIView):
    def get(self, request):
        if not _can(request, READ_ROLES):
            return Response({"detail": "Your current role cannot view outbound notifications."}, status=status.HTTP_403_FORBIDDEN)

        students = Student.objects.filter(is_active=True).select_related("current_class").prefetch_related(
            "bills__items", "bills__payments", "bills__fee_adjustments", "bills__applied_credits"
        ).order_by("student_name")[:3000]
        messages = OutboundMessage.objects.select_related("student").order_by("-created_at", "-id")[:250]
        return Response({
            "role": _role(request),
            "can_send_fee": _can(request, FEE_SEND_ROLES),
            "can_send_report": _can(request, REPORT_SEND_ROLES),
            "students": [_student_row(student) for student in students],
            "rows": [_message_row(message) for message in messages],
            "channels": [OutboundMessage.CHANNEL_SMS, OutboundMessage.CHANNEL_EMAIL, OutboundMessage.CHANNEL_WHATSAPP],
        })

    def post(self, request):
        action = str(request.data.get("action") or "").strip().lower()
        student_id = request.data.get("student_id")
        student = Student.objects.filter(pk=student_id, is_active=True).first()
        if not student:
            return Response({"detail": "Choose an active student."}, status=status.HTTP_400_BAD_REQUEST)

        if action == "preferences":
            if not _can(request, {"Admin", "Head Teacher", "Bursar"}):
                return Response({"detail": "Your current role cannot change communication preferences."}, status=status.HTTP_403_FORBIDDEN)
            preference, _ = CommunicationPreference.objects.get_or_create(student=student)
            preference.guardian_phone = str(request.data.get("guardian_phone") or student.contact or "").strip()
            preference.guardian_email = str(request.data.get("guardian_email") or "").strip()
            preference.whatsapp_number = str(request.data.get("whatsapp_number") or "").strip()
            preference.sms_enabled = bool(request.data.get("sms_enabled", True))
            preference.email_enabled = bool(request.data.get("email_enabled", True))
            preference.whatsapp_enabled = bool(request.data.get("whatsapp_enabled", False))
            preference.save()
            return Response({"detail": "Communication preferences saved.", "student": _student_row(student)})

        channel = str(request.data.get("channel") or OutboundMessage.CHANNEL_SMS).strip()
        valid_channels = {value for value, _label in OutboundMessage.CHANNEL_CHOICES}
        if channel not in valid_channels:
            return Response({"detail": "Choose SMS, Email or WhatsApp."}, status=status.HTTP_400_BAD_REQUEST)

        if action == "fee_reminder":
            if not _can(request, FEE_SEND_ROLES):
                return Response({"detail": "Your current role cannot send fee reminders."}, status=status.HTTP_403_FORBIDDEN)
            message = send_fee_balance_reminder(student, channel=channel)
            if message is None:
                return Response({"detail": "This student has no outstanding fee balance."}, status=status.HTTP_400_BAD_REQUEST)
        elif action == "report_notice":
            if not _can(request, REPORT_SEND_ROLES):
                return Response({"detail": "Your current role cannot send report notices."}, status=status.HTTP_403_FORBIDDEN)
            portal_url = str(request.data.get("portal_url") or "").strip()
            message = send_report_ready_notice(student, channel=channel, portal_url=portal_url)
        else:
            return Response({"detail": "Choose a supported notification action."}, status=status.HTTP_400_BAD_REQUEST)

        code = status.HTTP_200_OK if message.status == OutboundMessage.STATUS_SENT else status.HTTP_202_ACCEPTED
        return Response({
            "detail": f"{message.channel} notification is {message.status.lower()}.",
            "message": _message_row(message),
        }, status=code)
