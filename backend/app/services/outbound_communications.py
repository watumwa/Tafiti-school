import json
import os
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from app.models import CommunicationPreference, OutboundNotification


def _normalize_phone(value: str) -> str:
    text = "".join(ch for ch in str(value or "") if ch.isdigit() or ch == "+")
    if text.startswith("0"):
        text = "+256" + text[1:]
    elif text.startswith("256"):
        text = "+" + text
    return text


def _preference(student):
    preference, _ = CommunicationPreference.objects.get_or_create(
        student=student,
        defaults={"guardian_phone": student.contact},
    )
    if not preference.guardian_phone and student.contact:
        preference.guardian_phone = student.contact
        preference.save(update_fields=["guardian_phone"])
    return preference


def queue_message(student, channel, body, *, subject="", template_key="", recipient=""):
    preference = _preference(student)
    enabled = {
        OutboundNotification.CHANNEL_SMS: preference.sms_enabled,
        OutboundNotification.CHANNEL_EMAIL: preference.email_enabled,
        OutboundNotification.CHANNEL_WHATSAPP: preference.whatsapp_enabled,
    }.get(channel, False)

    if channel == OutboundNotification.CHANNEL_EMAIL:
        recipient = recipient or preference.guardian_email
    elif channel == OutboundNotification.CHANNEL_WHATSAPP:
        recipient = recipient or preference.whatsapp_number or preference.guardian_phone or student.contact
    else:
        recipient = recipient or preference.guardian_phone or student.contact

    message = OutboundNotification.objects.create(
        student=student,
        channel=channel,
        recipient=recipient,
        subject=subject,
        body=body,
        template_key=template_key,
    )
    if not preference.can_contact or not enabled or not recipient:
        message.status = OutboundNotification.STATUS_SKIPPED
        message.provider_response = "Recipient opted out, channel disabled, or no destination is configured."
        message.save(update_fields=["status", "provider_response"])
    return message


def _post_json(url, payload, headers=None, timeout=20):
    body = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        if value:
            req.add_header(key, value)
    with urllib_request.urlopen(req, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def deliver_message(message: OutboundNotification):
    if message.status == OutboundNotification.STATUS_SKIPPED:
        return message

    message.attempts += 1
    message.last_attempt_at = timezone.now()
    update_fields = ["attempts", "last_attempt_at"]

    try:
        if message.channel == OutboundNotification.CHANNEL_EMAIL:
            sent = send_mail(
                message.subject or "Tafiti School Notification",
                message.body,
                getattr(settings, "DEFAULT_FROM_EMAIL", None),
                [message.recipient],
                fail_silently=False,
            )
            if sent != 1:
                raise RuntimeError("Email backend did not confirm delivery submission.")
            response_text = "Email accepted by configured Django email backend."

        elif message.channel == OutboundNotification.CHANNEL_SMS:
            endpoint = (
                os.environ.get("SMS_PROVIDER_URL", "").strip()
                or os.environ.get("TAFITI_SMS_WEBHOOK_URL", "").strip()
            )
            if not endpoint:
                raise RuntimeError("SMS_PROVIDER_URL is not configured.")
            token = (
                os.environ.get("SMS_PROVIDER_TOKEN", "").strip()
                or os.environ.get("TAFITI_SMS_BEARER_TOKEN", "").strip()
            )
            sender_id = os.environ.get("SMS_SENDER_ID", "Tafiti").strip() or "Tafiti"
            status_code, response_text = _post_json(
                endpoint,
                {
                    "to": _normalize_phone(message.recipient),
                    "message": message.body,
                    "sender_id": sender_id,
                },
                headers={"Authorization": f"Bearer {token}" if token else ""},
            )
            if status_code >= 300:
                raise RuntimeError(f"SMS provider returned HTTP {status_code}: {response_text}")

        elif message.channel == OutboundNotification.CHANNEL_WHATSAPP:
            phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
            access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip()
            graph_version = os.environ.get("WHATSAPP_GRAPH_VERSION", "v20.0").strip() or "v20.0"
            if not phone_number_id or not access_token:
                raise RuntimeError("WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN must be configured.")
            endpoint = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages"
            status_code, response_text = _post_json(
                endpoint,
                {
                    "messaging_product": "whatsapp",
                    "to": _normalize_phone(message.recipient).lstrip("+"),
                    "type": "text",
                    "text": {"body": message.body},
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if status_code >= 300:
                raise RuntimeError(f"WhatsApp provider returned HTTP {status_code}: {response_text}")
        else:
            raise RuntimeError("Unsupported communication channel.")

        message.status = OutboundNotification.STATUS_SENT
        message.sent_at = timezone.now()
        message.provider_response = response_text[:4000]
        update_fields.extend(["status", "sent_at", "provider_response"])
    except (HTTPError, URLError, RuntimeError, OSError, ValueError) as exc:
        message.status = OutboundNotification.STATUS_FAILED
        message.provider_response = str(exc)[:4000]
        update_fields.extend(["status", "provider_response"])

    message.save(update_fields=update_fields)
    return message


def send_fee_balance_reminder(student, *, channel=OutboundNotification.CHANNEL_SMS):
    bills = student.bills.select_related("academic_class__term").order_by("-bill_date", "-id")
    outstanding = sum((max(bill.balance, 0) for bill in bills), 0)
    if outstanding <= 0:
        return None
    current = bills.first()
    term = str(current.academic_class.term) if current else "the current term"
    body = (
        f"Dear Parent/Guardian, {student.student_name} has an outstanding school-fee balance of "
        f"UGX {outstanding:,.0f} for {term}. Please contact the school bursar if you need clarification."
    )
    return deliver_message(queue_message(student, channel, body, template_key="fee_balance_reminder"))


def send_report_ready_notice(student, *, channel=OutboundNotification.CHANNEL_SMS, portal_url=""):
    body = f"Dear Parent/Guardian, {student.student_name}'s academic report is now available in the Tafiti Parent Portal."
    if portal_url:
        body += f" Open: {portal_url}"
    return deliver_message(queue_message(student, channel, body, template_key="report_ready"))
