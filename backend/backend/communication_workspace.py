from __future__ import annotations

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from app.forms.communications import AnnouncementForm, EventForm, MessageForm, MessageThreadForm
from app.models import (
    AcademicClassStream,
    Announcement,
    AnnouncementTarget,
    ClassSubjectAllocation,
    Event,
    Message,
    MessageThread,
    MessageThreadArchive,
    StaffAccount,
)

from .auth import canonical_role_label, resolve_active_role
from .workspace import WorkspaceBaseAPIView, _token_context
from .workspace_forms import (
    _choice_options,
    _field_type,
    _form_errors,
    _payload_to_querydict,
    _serialize_initial,
)


COMMUNICATION_ROLES = {
    "Admin", "Head Teacher", "Director of Studies", "Bursar", "Class Teacher", "Teacher",
    "Admissions Officer", "Librarian", "Library Assistant", "Support Staff", "Staff",
}


def _role(request) -> str:
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _allowed(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in COMMUNICATION_ROLES)


def _can_target_head(role: str) -> bool:
    return role not in {"Teacher", "Class Teacher"}


def _audiences(role: str):
    if role in {"Admin", "Head Teacher"}:
        return None
    if role == "Director of Studies":
        return ["all", "dos"]
    if role == "Bursar":
        return ["all", "bursar"]
    if role == "Class Teacher":
        return ["all", "class_teacher", "teachers"]
    if role == "Teacher":
        return ["all", "teachers"]
    return ["all"]


def _schema(form, *, title: str, submit_label: str, resource: str, mode="create"):
    fields = []
    for name, field in form.fields.items():
        initial = form.initial.get(name, field.initial)
        if callable(initial):
            initial = initial()
        fields.append({
            "name": name,
            "label": field.label or name.replace("_", " ").title(),
            "type": _field_type(field),
            "required": bool(field.required),
            "disabled": bool(field.disabled),
            "help_text": str(field.help_text or ""),
            "options": _choice_options(field),
            "initial": _serialize_initial(initial),
            "min_value": getattr(field, "min_value", None),
            "max_value": getattr(field, "max_value", None),
        })
    return {
        "resource": resource,
        "mode": mode,
        "title": title,
        "submit_label": submit_label,
        "fields": fields,
        "actions": {
            "view": True, "create": True, "edit": True, "delete": False,
            "create_label": submit_label, "edit_label": "Edit", "delete_label": "Delete",
        },
    }


def _announcement_form(request, instance=None, data=None):
    role = _role(request)
    return AnnouncementForm(
        data=data,
        instance=instance,
        can_target_head=_can_target_head(role),
        effective_role=role,
    )


def _event_form(request, instance=None, data=None):
    role = _role(request)
    return EventForm(
        data=data,
        instance=instance,
        can_target_head=_can_target_head(role),
        effective_role=role,
    )


def _visible_announcements(request):
    role = _role(request)
    audience = _audiences(role)
    now = timezone.now()
    queryset = Announcement.objects.all()
    if audience is not None:
        queryset = queryset.filter(audience__in=audience).exclude(audience="class_stream")
        queryset = queryset.filter(is_active=True, starts_at__lte=now).filter(
            Q(ends_at__isnull=True) | Q(ends_at__gte=now)
        )
    if role == "Class Teacher":
        account = StaffAccount.objects.filter(user=request.user).select_related("staff").first()
        if account and account.staff:
            class_streams = AcademicClassStream.objects.filter(class_teacher=account.staff)
            teacher_ids = ClassSubjectAllocation.objects.filter(
                is_active=True,
                academic_class_stream__in=class_streams,
            ).values_list("subject_teacher_id", flat=True)
            queryset = queryset | Announcement.objects.filter(
                audience="class_stream",
                targets__staff_id__in=teacher_ids,
                is_active=True,
                starts_at__lte=now,
            ).filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
    return queryset.distinct().order_by("-starts_at", "-created_at")


def _visible_events(request):
    role = _role(request)
    audience = _audiences(role)
    queryset = Event.objects.all()
    if audience is not None:
        queryset = queryset.filter(audience__in=audience, is_active=True, start_datetime__gte=timezone.now())
    return queryset.order_by("start_datetime", "title")


def _thread_row(request, thread: MessageThread):
    participants = list(thread.participants.all())
    others = [user for user in participants if user.pk != request.user.pk]
    last = thread.messages.order_by("-created_at").first()
    return {
        "id": thread.pk,
        "subject": thread.subject or "Conversation",
        "participants": ", ".join((user.get_full_name() or user.username) for user in others) or "Only you",
        "preview": (last.body[:140] if last else "No messages yet"),
        "last_sender": (last.sender.get_full_name() or last.sender.username) if last and last.sender else "System",
        "updated": thread.updated_at.isoformat(),
        "archived": MessageThreadArchive.objects.filter(thread=thread, user=request.user).exists(),
    }


class CommunicationConsoleAPIView(WorkspaceBaseAPIView):
    def _guard(self, request):
        if _allowed(request):
            return None
        return Response({"detail": "Your current role cannot access communication."}, status=status.HTTP_403_FORBIDDEN)

    def get(self, request, screen: str, pk: int | None = None):
        failure = self._guard(request)
        if failure:
            return failure
        role = _role(request)

        if screen == "announcements":
            rows = [{
                "id": row.pk,
                "title": row.title,
                "body": row.body,
                "audience": row.get_audience_display(),
                "priority": row.get_priority_display(),
                "starts": row.starts_at.isoformat(),
                "ends": row.ends_at.isoformat() if row.ends_at else "",
                "status": "Active" if row.is_active else "Inactive",
                "created_by": str(row.created_by or "System"),
            } for row in _visible_announcements(request)[:1000]]
            form = _announcement_form(request, instance=Announcement.objects.filter(pk=pk).first()) if pk else _announcement_form(request)
            return Response({
                "rows": rows,
                "form": _schema(form, title="Edit announcement" if pk else "New announcement", submit_label="Save announcement" if pk else "Publish announcement", resource="communication-announcement", mode="edit" if pk else "create"),
            })

        if screen == "events":
            rows = [{
                "id": row.pk,
                "title": row.title,
                "description": row.description,
                "audience": row.get_audience_display(),
                "location": row.location or "—",
                "starts": row.start_datetime.isoformat(),
                "ends": row.end_datetime.isoformat() if row.end_datetime else "",
                "status": "Active" if row.is_active else "Inactive",
            } for row in _visible_events(request)[:1000]]
            form = _event_form(request, instance=Event.objects.filter(pk=pk).first()) if pk else _event_form(request)
            return Response({
                "rows": rows,
                "form": _schema(form, title="Edit event" if pk else "New event", submit_label="Save event", resource="communication-event", mode="edit" if pk else "create"),
            })

        if screen == "messages":
            show_archived = request.query_params.get("archived") in {"1", "true"}
            archive_ids = MessageThreadArchive.objects.filter(user=request.user).values_list("thread_id", flat=True)
            threads = MessageThread.objects.filter(participants=request.user).distinct()
            threads = threads.filter(id__in=archive_ids) if show_archived else threads.exclude(id__in=archive_ids)
            threads = threads.prefetch_related("participants", "messages__sender").order_by("-updated_at")[:1000]
            form = MessageThreadForm(sender=request.user, effective_role=role)
            return Response({
                "rows": [_thread_row(request, thread) for thread in threads],
                "archived": show_archived,
                "form": _schema(form, title="New conversation", submit_label="Start conversation", resource="communication-message"),
            })

        if screen == "thread":
            if pk is None:
                return Response({"detail": "Choose a conversation."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                thread = MessageThread.objects.prefetch_related("participants", "messages__sender").get(pk=pk, participants=request.user)
            except MessageThread.DoesNotExist:
                return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)
            return Response({
                "thread": _thread_row(request, thread),
                "messages": [{
                    "id": message.pk,
                    "sender": (message.sender.get_full_name() or message.sender.username) if message.sender else "System",
                    "sender_id": message.sender_id,
                    "mine": message.sender_id == request.user.pk,
                    "body": message.body,
                    "created": message.created_at.isoformat(),
                } for message in thread.messages.all()],
                "form": _schema(MessageForm(), title="Reply", submit_label="Send message", resource="communication-reply"),
            })

        return Response({"detail": "Communication workspace not found."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, screen: str, pk: int | None = None):
        failure = self._guard(request)
        if failure:
            return failure
        role = _role(request)
        payload = request.data if hasattr(request.data, "getlist") else _payload_to_querydict(dict(request.data))

        if screen == "announcements":
            instance = Announcement.objects.filter(pk=pk).first() if pk else None
            if pk and not instance:
                return Response({"detail": "Announcement not found."}, status=status.HTTP_404_NOT_FOUND)
            form = _announcement_form(request, instance=instance, data=payload)
            if not form.is_valid():
                return Response({"detail": "Check the announcement fields.", "errors": _form_errors(form)}, status=status.HTTP_400_BAD_REQUEST)
            announcement = form.save(commit=False)
            if not _can_target_head(role) and announcement.audience == "head":
                return Response({"detail": "Teachers cannot target Head Teacher."}, status=status.HTTP_403_FORBIDDEN)
            if announcement.audience == "class_stream" and role != "Class Teacher":
                return Response({"detail": "Only Class Teachers can target class stream teachers."}, status=status.HTTP_403_FORBIDDEN)
            if not instance:
                announcement.created_by = request.user
            with transaction.atomic():
                announcement.save()
                if announcement.audience == "class_stream":
                    announcement.targets.all().delete()
                    account = StaffAccount.objects.filter(user=request.user).select_related("staff").first()
                    if account and account.staff:
                        class_streams = AcademicClassStream.objects.filter(class_teacher=account.staff)
                        teacher_ids = ClassSubjectAllocation.objects.filter(
                            is_active=True, academic_class_stream__in=class_streams
                        ).values_list("subject_teacher_id", flat=True)
                        AnnouncementTarget.objects.bulk_create([
                            AnnouncementTarget(announcement=announcement, staff_id=teacher_id)
                            for teacher_id in teacher_ids
                        ])
            return Response({"detail": "Announcement saved successfully.", "id": announcement.pk})

        if screen == "events":
            instance = Event.objects.filter(pk=pk).first() if pk else None
            if pk and not instance:
                return Response({"detail": "Event not found."}, status=status.HTTP_404_NOT_FOUND)
            form = _event_form(request, instance=instance, data=payload)
            if not form.is_valid():
                return Response({"detail": "Check the event fields.", "errors": _form_errors(form)}, status=status.HTTP_400_BAD_REQUEST)
            event = form.save(commit=False)
            if not _can_target_head(role) and event.audience == "head":
                return Response({"detail": "Teachers cannot target Head Teacher."}, status=status.HTTP_403_FORBIDDEN)
            if not instance:
                event.created_by = request.user
            event.save()
            return Response({"detail": "Event saved successfully.", "id": event.pk})

        if screen == "messages":
            body = str(request.data.get("body") or "").strip()
            form = MessageThreadForm(payload, sender=request.user, effective_role=role)
            if not form.is_valid():
                return Response({"detail": "Check the recipients and subject.", "errors": _form_errors(form)}, status=status.HTTP_400_BAD_REQUEST)
            recipients = list(form.cleaned_data["recipients"])
            participant_users = [request.user] + [recipient.user for recipient in recipients]
            thread_query = MessageThread.objects.filter(participants=request.user).distinct()
            for user in participant_users[1:]:
                thread_query = thread_query.filter(participants=user)
            thread = thread_query.annotate(p_count=Count("participants")).filter(p_count=len(participant_users)).first()
            with transaction.atomic():
                if not thread:
                    thread = MessageThread.objects.create(subject=form.cleaned_data.get("subject", ""), created_by=request.user)
                    thread.participants.add(*participant_users)
                if body:
                    Message.objects.create(thread=thread, sender=request.user, body=body)
                    thread.updated_at = timezone.now()
                    thread.save(update_fields=["updated_at"])
                MessageThreadArchive.objects.filter(thread=thread, user=request.user).delete()
            return Response({"detail": "Conversation opened successfully.", "id": thread.pk})

        if screen == "thread":
            if pk is None:
                return Response({"detail": "Choose a conversation."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                thread = MessageThread.objects.get(pk=pk, participants=request.user)
            except MessageThread.DoesNotExist:
                return Response({"detail": "Conversation not found."}, status=status.HTTP_404_NOT_FOUND)
            action = str(request.data.get("action") or "reply")
            if action == "archive":
                MessageThreadArchive.objects.get_or_create(thread=thread, user=request.user)
                return Response({"detail": "Conversation archived."})
            if action == "unarchive":
                MessageThreadArchive.objects.filter(thread=thread, user=request.user).delete()
                return Response({"detail": "Conversation restored to inbox."})
            if action == "delete-message":
                message_id = request.data.get("message_id")
                deleted, _ = Message.objects.filter(pk=message_id, sender=request.user, thread=thread).delete()
                if not deleted:
                    return Response({"detail": "You can only delete your own message."}, status=status.HTTP_403_FORBIDDEN)
                return Response({"detail": "Message deleted."})
            form = MessageForm(payload)
            if not form.is_valid():
                return Response({"detail": "Enter a message before sending.", "errors": _form_errors(form)}, status=status.HTTP_400_BAD_REQUEST)
            message = form.save(commit=False)
            message.thread = thread
            message.sender = request.user
            message.save()
            thread.updated_at = timezone.now()
            thread.save(update_fields=["updated_at"])
            MessageThreadArchive.objects.filter(thread=thread, user=request.user).delete()
            return Response({"detail": "Message sent.", "id": message.pk})

        return Response({"detail": "Communication action not found."}, status=status.HTTP_404_NOT_FOUND)
