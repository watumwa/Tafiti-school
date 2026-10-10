import json
import os
from decimal import Decimal
from urllib import error, request

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from app.models import OutboundDelivery, OutboundMessage


def _send_email(delivery, message):
    sent = send_mail(
        subject=message.subject or "School notification",
        message=message.body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[delivery.destination],
        fail_silently=False,
    )
    if not sent:
        raise RuntimeError("Email provider did not accept the message.")
    return "django-email", Decimal("0")


def _send_sms(delivery, message):
    endpoint = str(os.environ.get("SMS_PROVIDER_URL", getattr(settings, "SMS_PROVIDER_URL", "")) or "").strip()
    token = str(os.environ.get("SMS_PROVIDER_TOKEN", getattr(settings, "SMS_PROVIDER_TOKEN", "")) or "").strip()
    sender = str(os.environ.get("SMS_SENDER_ID", getattr(settings, "SMS_SENDER_ID", "Tafiti")) or "Tafiti").strip()
    if not endpoint or not token:
        raise RuntimeError("SMS provider is not configured. Set SMS_PROVIDER_URL and SMS_PROVIDER_TOKEN.")

    payload = json.dumps({
        "to": delivery.destination,
        "message": message.body,
        "sender_id": sender,
    }).encode("utf-8")
    req = request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            raw = response.read().decode("utf-8", errors="replace")
            if not 200 <= response.status < 300:
                raise RuntimeError(f"SMS provider returned HTTP {response.status}.")
    except error.HTTPError as exc:
        raise RuntimeError(f"SMS provider returned HTTP {exc.code}.") from exc
    except error.URLError as exc:
        raise RuntimeError("SMS provider could not be reached.") from exc

    provider_ref = "sms-provider"
    cost = Decimal("0")
    try:
        data = json.loads(raw or "{}")
        provider_ref = str(data.get("id") or data.get("message_id") or provider_ref)
        cost = Decimal(str(data.get("cost") or 0))
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    return provider_ref, cost


@transaction.atomic
def process_outbound_messages(*, limit=100):
    deliveries = list(
        OutboundDelivery.objects.select_for_update(skip_locked=True)
        .select_related("message")
        .filter(status=OutboundDelivery.STATUS_QUEUED, consented=True)
        .order_by("id")[:limit]
    )
    sent = failed = 0
    affected_messages = set()

    for delivery in deliveries:
        message = delivery.message
        affected_messages.add(message.pk)
        message.status = OutboundMessage.STATUS_PROCESSING
        message.save(update_fields=("status",))
        try:
            if delivery.channel == "email":
                provider_ref, cost = _send_email(delivery, message)
            else:
                provider_ref, cost = _send_sms(delivery, message)
            delivery.status = OutboundDelivery.STATUS_SENT
            delivery.provider_reference = provider_ref
            delivery.cost = cost
            delivery.error_message = ""
            delivery.sent_at = timezone.now()
            sent += 1
        except Exception as exc:
            delivery.retry_count += 1
            delivery.error_message = str(exc)[:1000]
            delivery.status = OutboundDelivery.STATUS_FAILED if delivery.retry_count >= 3 else OutboundDelivery.STATUS_QUEUED
            failed += 1
        delivery.save(update_fields=("status", "provider_reference", "cost", "error_message", "sent_at", "retry_count"))

    for message in OutboundMessage.objects.filter(pk__in=affected_messages).prefetch_related("deliveries"):
        active = message.deliveries.exclude(status=OutboundDelivery.STATUS_SKIPPED)
        total = active.count()
        sent_count = active.filter(status__in=(OutboundDelivery.STATUS_SENT, OutboundDelivery.STATUS_DELIVERED)).count()
        failed_count = active.filter(status=OutboundDelivery.STATUS_FAILED).count()
        queued_count = active.filter(status=OutboundDelivery.STATUS_QUEUED).count()
        message.actual_cost = sum((row.cost for row in active), Decimal("0"))
        if total and sent_count == total:
            message.status = OutboundMessage.STATUS_SENT
            message.processed_at = timezone.now()
        elif failed_count and not queued_count:
            message.status = OutboundMessage.STATUS_PARTIAL if sent_count else OutboundMessage.STATUS_FAILED
            message.processed_at = timezone.now()
        else:
            message.status = OutboundMessage.STATUS_PROCESSING
        message.save(update_fields=("status", "actual_cost", "processed_at"))

    return {"processed": len(deliveries), "sent": sent, "failed": failed}
