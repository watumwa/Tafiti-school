import calendar
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from app.decorators.decorators import role_required_any
from app.decorators.features import feature_required
from app.decorators.parent_portal import parent_required
from app.forms.parent_portal import (
    ParentAccessPermissionsForm, ParentConversationStartForm, ParentFirstPasswordForm,
    ParentLoginForm, ParentMessageForm,
)
from app.models import (
    Announcement, AttendanceRecord, Event, LibraryLoan, Message, ParentAccess, ParentConversation,
    LibraryFine, ParentNotification, ParentPortalAudit, Payment, ReportCycleRemark, ReportRemark, Result,
    SchoolSetting, Student, StudentDocument, Term,
)
from app.services.parent_experience import (
    attendance_for,
    child_summary,
    current_academic_term,
    subject_performance,
    timetable_for_student,
    verified_results_for,
)
from app.services.parent_portal import (
    ParentAccessError, activate_parent_access, active_parent_accesses, client_ip,
    deactivate_parent_access, eligible_parent_teachers, parent_username, reset_parent_password,
    start_parent_conversation, sync_parent_notifications,
)
from app.utils.pdf_utils import generate_student_report_pdf


PARENT_MANAGEMENT_ROLES = ("Admin", "Head Teacher", "Head master", "Director of Studies")


def _rate_key(request, phone):
    return f"parent-login:{client_ip(request)}:{phone}"


@feature_required("PARENT_PORTAL_ENABLED")
def parent_login(request):
    if request.user.is_authenticated and active_parent_accesses(request.user).exists():
        return redirect("parent_dashboard")
    form = ParentLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            username = parent_username(form.cleaned_data["phone"])
        except ParentAccessError:
            username = ""
        key = _rate_key(request, username)
        failures = int(cache.get(key, 0))
        if failures >= settings.PARENT_LOGIN_MAX_ATTEMPTS:
            form.add_error(None, "Too many failed attempts. Try again later or contact the school.")
        else:
            user = authenticate(request, username=username, password=form.cleaned_data["password"])
            accesses = active_parent_accesses(user) if user else ParentAccess.objects.none()
            expired = bool(user and accesses.filter(must_change_password=True, temporary_password_expires_at__lte=timezone.now()).exists())
            if user and accesses.exists() and not expired:
                cache.delete(key)
                login(request, user)
                ParentPortalAudit.objects.create(user=user, action=ParentPortalAudit.ACTION_LOGIN, ip_address=client_ip(request))
                return redirect("parent_force_password" if accesses.filter(must_change_password=True).exists() else "parent_dashboard")
            cache.set(key, failures + 1, settings.PARENT_LOGIN_LOCK_SECONDS)
            ParentPortalAudit.objects.create(
                user=user, action=ParentPortalAudit.ACTION_LOGIN_FAILED, ip_address=client_ip(request),
                details={"username": username, "expired": expired},
            )
            form.add_error(None, "Invalid or expired credentials. Contact the school if this continues.")
    return render(request, "parent_portal/login.html", {"form": form, "portal_guest": True})


@feature_required("PARENT_PORTAL_ENABLED")
@login_required(login_url="parent_login")
def parent_force_password(request):
    accesses = active_parent_accesses(request.user)
    if not accesses.exists():
        return redirect("parent_login")
    if not accesses.filter(must_change_password=True).exists():
        return redirect("parent_dashboard")
    if accesses.filter(temporary_password_expires_at__lte=timezone.now()).exists():
        logout(request)
        messages.error(request, "The temporary password expired. Ask the school to reactivate access.")
        return redirect("parent_login")
    form = ParentFirstPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        request.user.set_password(form.cleaned_data["password"])
        request.user.save(update_fields=["password"])
        accesses.update(must_change_password=False, temporary_password_expires_at=None)
        ParentPortalAudit.objects.create(user=request.user, action=ParentPortalAudit.ACTION_PASSWORD_CHANGED, ip_address=client_ip(request))
        update_session_auth_hash(request, request.user)
        return redirect("parent_dashboard")
    return render(request, "parent_portal/force_password.html", {"form": form, "portal_guest": True})


def _selected_access(request, student_id=None):
    qs = getattr(request, "parent_accesses", active_parent_accesses(request.user))
    return get_object_or_404(qs, student_id=student_id) if student_id else qs.first()


def _as_activity_datetime(value):
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value)
    return timezone.make_aware(datetime.combine(value, time.min))


def _selected_month(value):
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except (TypeError, ValueError):
        today = timezone.localdate()
        return today.replace(day=1)


def _shift_month(month, offset):
    index = month.year * 12 + month.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def _calendar_rows(month, values_by_date):
    today = timezone.localdate()
    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(month.year, month.month):
        weeks.append([
            {
                "date": day,
                "in_month": day.month == month.month,
                "is_today": day == today,
                "values": values_by_date.get(day, []),
            }
            for day in week
        ])
    return weeks


def _visible_student_documents(access):
    documents = StudentDocument.objects.filter(student=access.student)
    if not access.can_view_finance:
        documents = documents.filter(bill__isnull=True)
    return documents


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_dashboard(request):
    sync_parent_notifications(request.user)
    selected = request.GET.get("student", "") or str(request.session.get("parent_selected_student_id", ""))
    access = request.parent_accesses.filter(student_id=int(selected)).first() if selected.isdigit() else None
    access = access or _selected_access(request)
    student = access.student
    request.session["parent_selected_student_id"] = student.id
    current_term = current_academic_term()
    child_rows = [child_summary(row, current_term) for row in request.parent_accesses]
    selected_summary = next(row for row in child_rows if row["student"].id == student.id)

    attendance_values = [row["attendance_percent"] for row in child_rows if row["attendance_percent"] is not None]
    family_attendance = round(sum(attendance_values) / len(attendance_values), 1) if attendance_values else None
    total_balance = sum((max(row["balance"], Decimal("0")) for row in child_rows), Decimal("0"))

    today = timezone.localdate()
    weekday = today.strftime("%a").upper()[:3]
    today_schedule = []
    for row in child_rows:
        entries, _class_stream = timetable_for_student(row["student"], current_term, weekday)
        for entry in entries:
            today_schedule.append({"student": row["student"], "entry": entry})
    today_schedule.sort(key=lambda item: item["entry"].time_slot.start_time)

    now = timezone.now()
    upcoming_events = Event.objects.filter(
        is_active=True,
        audience__in=("all", "parents"),
        start_datetime__gte=now,
        start_datetime__lte=now + timedelta(days=45),
    ).order_by("start_datetime")[:6]

    action_items = []
    for row in child_rows:
        if row["access"].can_view_finance and row["balance"] > 0:
            action_items.append({
                "kind": "fees", "priority": "danger", "icon": "ph-wallet",
                "title": f"Fees outstanding for {row['student'].student_name}",
                "description": f"UGX {row['balance']:,.0f} remains unpaid.",
                "url": reverse("parent_finance", args=[row["student"].id]), "action": "View fees",
            })
        if row["overdue_loan_count"]:
            action_items.append({
                "kind": "library", "priority": "warning", "icon": "ph-book-open",
                "title": f"Overdue library book for {row['student'].student_name}",
                "description": f"{row['overdue_loan_count']} book(s) need attention.",
                "url": reverse("parent_library", args=[row["student"].id]), "action": "Review loan",
            })

    activities = []
    finance_student_ids = [row["student"].id for row in child_rows if row["access"].can_view_finance]
    academic_student_ids = [row["student"].id for row in child_rows if row["access"].can_view_academics]
    for payment in Payment.objects.filter(bill__student_id__in=finance_student_ids).select_related("bill__student").order_by("-payment_date", "-id")[:6]:
        activities.append({
            "when": _as_activity_datetime(payment.payment_date), "icon": "ph-receipt", "tone": "success",
            "title": "Fee payment recorded", "description": f"{payment.bill.student.student_name} · UGX {payment.amount:,.0f}",
            "url": reverse("parent_payment_receipt", args=[payment.bill.student_id, payment.id]),
        })
    for result in Result.objects.filter(student_id__in=academic_student_ids, status="VERIFIED").select_related("student", "assessment__subject").order_by("-assessment__date", "-id")[:6]:
        activities.append({
            "when": _as_activity_datetime(result.assessment.date), "icon": "ph-chart-line-up", "tone": "info",
            "title": f"{result.assessment.subject} result published", "description": result.student.student_name,
            "url": reverse("parent_results", args=[result.student_id]),
        })

    activities.sort(key=lambda item: item["when"], reverse=True)
    notifications = ParentNotification.objects.filter(user=request.user, read_at__isnull=True).select_related("student")[:6]
    return render(request, "parent_portal/dashboard.html", {
        "children": request.parent_accesses, "access": access, "student": student,
        "child_rows": child_rows, "selected_summary": selected_summary,
        "family_attendance": family_attendance, "total_balance": total_balance,
        "today_schedule": today_schedule, "upcoming_events": upcoming_events,
        "action_items": action_items[:6], "activities": activities[:8], "notifications": notifications,
        "current_term": current_term,
    })


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_children(request):
    current_term = current_academic_term()
    children = [child_summary(access, current_term) for access in request.parent_accesses]
    return render(request, "parent_portal/children.html", {"children": children, "current_term": current_term})


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_child_overview(request, student_id):
    access = _selected_access(request, student_id)
    current_term = current_academic_term()
    summary = child_summary(access, current_term)
    schedule, class_stream = timetable_for_student(access.student, current_term)
    return render(request, "parent_portal/child_overview.html", {
        "access": access, "student": access.student, "summary": summary, "current_term": current_term,
        "schedule": schedule, "class_stream": class_stream, "children": request.parent_accesses,
    })


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_results(request, student_id):
    access = _selected_access(request, student_id)
    if not access.can_view_academics:
        messages.warning(request, "Academic results are not enabled for this child.")
        return redirect("parent_dashboard")
    term_id = request.GET.get("term_id", "")
    current_term = current_academic_term()
    term = Term.objects.filter(pk=int(term_id)).first() if term_id.isdigit() else current_term
    results = verified_results_for(access.student, term)
    performance = subject_performance(results)
    terms = Term.objects.filter(
        academicclass__result__student=access.student, academicclass__result__status="VERIFIED"
    ).distinct().order_by("-academic_year__academic_year", "term")
    return render(request, "parent_portal/results.html", {
        "access": access, "student": access.student, "results": results, "performance": performance,
        "terms": terms, "selected_term": term, "current_term": current_term, "children": request.parent_accesses,
    })


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_attendance(request, student_id):
    access = _selected_access(request, student_id)
    if not access.can_view_attendance:
        messages.warning(request, "Attendance is not enabled for this child.")
        return redirect("parent_dashboard")
    month = _selected_month(request.GET.get("month"))
    records = attendance_for(access.student).filter(session__attendance_date__year=month.year, session__attendance_date__month=month.month)
    by_date = defaultdict(list)
    for record in records:
        by_date[record.session.attendance_date].append(record)
    return render(request, "parent_portal/attendance.html", {
        "access": access, "student": access.student, "records": records, "calendar_rows": _calendar_rows(month, by_date),
        "month": month, "previous_month": _shift_month(month, -1), "next_month": _shift_month(month, 1),
        "children": request.parent_accesses,
    })


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_finance(request, student_id):
    access = _selected_access(request, student_id)
    if not access.can_view_finance:
        messages.warning(request, "Finance information is not enabled for this child.")
        return redirect("parent_dashboard")
    bills = access.student.bills.select_related("academic_class").prefetch_related("items", "payments").order_by("-academic_class__academic_year__academic_year")
    return render(request, "parent_portal/finance.html", {
        "access": access, "student": access.student, "bills": bills, "children": request.parent_accesses,
    })


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_payment_receipt(request, student_id, payment_id):
    access = _selected_access(request, student_id)
    if not access.can_view_finance:
        raise Http404
    payment = get_object_or_404(Payment.objects.select_related("bill__student", "bill__academic_class"), pk=payment_id, bill__student=access.student)
    school = SchoolSetting.objects.first()
    return render(request, "parent_portal/payment_receipt.html", {
        "access": access, "student": access.student, "payment": payment, "school": school,
        "children": request.parent_accesses,
    })


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_timetable(request, student_id):
    access = _selected_access(request, student_id)
    current_term = current_academic_term()
    schedule, class_stream = timetable_for_student(access.student, current_term)
    grouped = defaultdict(list)
    for row in schedule:
        grouped[row.weekday].append(row)
    return render(request, "parent_portal/timetable.html", {
        "access": access, "student": access.student, "schedule": schedule, "grouped": dict(grouped),
        "class_stream": class_stream, "current_term": current_term, "children": request.parent_accesses,
    })


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_documents(request, student_id):
    access = _selected_access(request, student_id)
    documents = _visible_student_documents(access).order_by("-uploaded_at")
    payments = Payment.objects.filter(bill__student=access.student).select_related("bill").order_by("-payment_date", "-id") if access.can_view_finance else Payment.objects.none()
    return render(request, "parent_portal/documents.html", {
        "access": access, "student": access.student, "documents": documents, "payments": payments,
        "children": request.parent_accesses,
    })


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_calendar(request):
    month = _selected_month(request.GET.get("month"))
    start = timezone.make_aware(datetime.combine(month, time.min))
    next_month = _shift_month(month, 1)
    end = timezone.make_aware(datetime.combine(next_month, time.min))
    events = Event.objects.filter(
        is_active=True, audience__in=("all", "parents"), start_datetime__gte=start, start_datetime__lt=end,
    ).order_by("start_datetime")
    by_date = defaultdict(list)
    for event in events:
        by_date[timezone.localtime(event.start_datetime).date()].append(event)
    return render(request, "parent_portal/calendar.html", {
        "calendar_rows": _calendar_rows(month, by_date), "month": month,
        "previous_month": _shift_month(month, -1), "next_month": next_month,
        "children": request.parent_accesses,
    })


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_announcements(request):
    now = timezone.now()
    announcements = Announcement.objects.filter(
        is_active=True, audience__in=("all", "parents"), starts_at__lte=now,
    ).filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
    return render(request, "parent_portal/announcements.html", {"announcements": announcements, "children": request.parent_accesses})


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_library(request, student_id):
    access = _selected_access(request, student_id)
    if not getattr(settings, "LIBRARY_ENABLED", False):
        return redirect("parent_dashboard")
    loans = LibraryLoan.objects.filter(student=access.student).select_related("copy__book").order_by("-issued_at")
    fines = LibraryFine.objects.filter(loan__student=access.student).select_related("loan__copy__book")
    return render(request, "parent_portal/library.html", {
        "access": access, "student": access.student, "current_loans": loans.filter(returned_at__isnull=True),
        "history": loans.filter(returned_at__isnull=False)[:30], "fines": fines,
        "children": request.parent_accesses,
    })


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_report_download(request, student_id):
    access = _selected_access(request, student_id)
    if not access.can_view_academics:
        return redirect("parent_dashboard")
    term_id = request.GET.get("term_id", "")
    results = Result.objects.filter(student=access.student, status="VERIFIED").select_related(
        "assessment__subject", "assessment__assessment_type"
    ).order_by("assessment__subject__name", "assessment__date")
    if term_id.isdigit():
        results = results.filter(assessment__academic_class__term_id=int(term_id))
    else:
        current_term = Term.objects.filter(is_current=True).order_by("id").first()
        if current_term:
            results = results.filter(assessment__academic_class__term=current_term)
    if not results.exists():
        messages.error(request, "No verified results are available for this report.")
        return redirect("parent_results", student_id=student_id)
    buffer = generate_student_report_pdf(access.student, results)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{access.student.reg_no}-verified-results.pdf"'
    ParentPortalAudit.objects.create(
        user=request.user, student=access.student, action=ParentPortalAudit.ACTION_VIEWED,
        ip_address=client_ip(request), details={"page": "report_download", "term_id": term_id},
    )
    return response


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_notifications(request):
    sync_parent_notifications(request.user)
    notifications = ParentNotification.objects.filter(user=request.user).select_related("student")
    return render(request, "parent_portal/notifications.html", {"notifications": notifications, "children": request.parent_accesses})


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_notification_open(request, notification_id):
    notification = get_object_or_404(ParentNotification, pk=notification_id, user=request.user)
    if not notification.read_at:
        notification.read_at = timezone.now()
        notification.save(update_fields=("read_at",))
    return redirect(notification.destination or "parent_notifications")


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_messages(request):
    conversations = ParentConversation.objects.filter(
        parent=request.user, student_id__in=request.parent_accesses.values("student_id"), is_active=True,
    ).select_related("student", "staff", "thread").prefetch_related("thread__messages")
    return render(request, "parent_portal/messages.html", {"conversations": conversations, "children": request.parent_accesses})


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_message_new(request, student_id):
    access = _selected_access(request, student_id)
    teachers = eligible_parent_teachers(access.student)
    form = ParentConversationStartForm(request.POST or None, teachers=teachers)
    if request.method == "POST" and form.is_valid():
        try:
            conversation = start_parent_conversation(
                parent=request.user, student=access.student, teacher=form.cleaned_data["teacher"],
                subject=form.cleaned_data["subject"], body=form.cleaned_data["message"],
            )
            return redirect("parent_message_thread", conversation_id=conversation.pk)
        except ParentAccessError as exc:
            form.add_error(None, str(exc))
    return render(request, "parent_portal/message_new.html", {
        "form": form, "access": access, "student": access.student, "children": request.parent_accesses,
    })


@feature_required("PARENT_PORTAL_ENABLED")
@parent_required
def parent_message_thread(request, conversation_id):
    conversation = get_object_or_404(
        ParentConversation.objects.select_related("thread", "student", "staff"),
        pk=conversation_id, parent=request.user, is_active=True,
        student_id__in=request.parent_accesses.values("student_id"),
    )
    form = ParentMessageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        message = form.save(commit=False)
        message.thread = conversation.thread
        message.sender = request.user
        message.save()
        conversation.thread.updated_at = timezone.now()
        conversation.thread.save(update_fields=("updated_at",))
        return redirect("parent_message_thread", conversation_id=conversation.pk)
    return render(request, "parent_portal/message_thread.html", {
        "conversation": conversation, "thread_messages": conversation.thread.messages.select_related("sender"),
        "form": form, "children": request.parent_accesses,
    })


@feature_required("PARENT_PORTAL_ENABLED")
@role_required_any(*PARENT_MANAGEMENT_ROLES)
def parent_access_activate(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    if request.method == "POST":
        try:
            access = activate_parent_access(
                student=student, verified_by=request.user,
                allow_guardian_mismatch=request.POST.get("confirm_shared_contact") == "yes",
            )
            temporary_password = getattr(access, "_temporary_password", None)
            if access.must_change_password and temporary_password:
                notice = (
                    f"Username: {access.user.username}; one-time password: {temporary_password} "
                    f"(expires in {settings.PARENT_TEMP_PASSWORD_HOURS} hours). Share it privately; it will not be shown again."
                )
            else:
                notice = f"Linked to the existing parent account {access.user.username}; its private password was not changed."
            messages.success(request, f"Parent access activated. {notice}")
        except ParentAccessError as exc:
            messages.error(request, str(exc))
    return redirect("student_details_page", id=student.pk)


@feature_required("PARENT_PORTAL_ENABLED")
@role_required_any(*PARENT_MANAGEMENT_ROLES)
def parent_access_management(request):
    accesses = ParentAccess.objects.select_related("user", "student", "verified_by").order_by(
        "user__username", "student__student_name"
    )
    query = request.GET.get("q", "").strip()
    if query:
        accesses = accesses.filter(
            Q(user__username__icontains=query) | Q(student__student_name__icontains=query)
            | Q(student__reg_no__icontains=query) | Q(student__guardian__icontains=query)
        )
    return render(request, "parent_portal/manage.html", {"accesses": accesses, "query": query})


@feature_required("PARENT_PORTAL_ENABLED")
@role_required_any(*PARENT_MANAGEMENT_ROLES)
def parent_access_update(request, access_id):
    access = get_object_or_404(ParentAccess.objects.select_related("student", "user"), pk=access_id)
    if request.method == "POST":
        form = ParentAccessPermissionsForm(request.POST, instance=access)
        if form.is_valid():
            form.save()
            ParentPortalAudit.objects.create(
                user=access.user, student=access.student, action=ParentPortalAudit.ACTION_ACCESS_CHANGED,
                details={"actor": request.user.pk, "permissions": form.cleaned_data},
            )
            messages.success(request, "Parent portal permissions updated.")
            return redirect("parent_access_management")
    else:
        form = ParentAccessPermissionsForm(instance=access)
    return render(request, "parent_portal/access_form.html", {"access": access, "form": form})


@feature_required("PARENT_PORTAL_ENABLED")
@role_required_any(*PARENT_MANAGEMENT_ROLES)
def parent_access_deactivate(request, access_id):
    if request.method == "POST":
        deactivate_parent_access(access_id=access_id, actor=request.user, reason=request.POST.get("reason", ""))
        messages.success(request, "The selected parent-to-student access was deactivated.")
    return redirect("parent_access_management")


@feature_required("PARENT_PORTAL_ENABLED")
@role_required_any(*PARENT_MANAGEMENT_ROLES)
def parent_password_reset(request, user_id):
    if request.method == "POST":
        try:
            user = reset_parent_password(user_id=user_id, actor=request.user)
            temporary_password = getattr(user, "_temporary_password", None)
            messages.success(
                request,
                f"Password reset for {user.username}. One-time password: {temporary_password}; it expires in "
                f"{settings.PARENT_TEMP_PASSWORD_HOURS} hours. Share it privately; it will not be shown again.",
            )
        except ParentAccessError as exc:
            messages.error(request, str(exc))
    return redirect("parent_access_management")


@feature_required("PARENT_PORTAL_ENABLED")
def parent_logout(request):
    if request.user.is_authenticated:
        ParentPortalAudit.objects.create(user=request.user, action=ParentPortalAudit.ACTION_LOGOUT, ip_address=client_ip(request))
    logout(request)
    return redirect("parent_login")
