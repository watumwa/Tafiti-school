from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from app.decorators.decorators import role_required_any
from app.decorators.features import feature_required
from app.forms.admissions import AdmissionApplicationForm, PublicAdmissionApplicationForm, PublicAdmissionTrackingForm
from app.models import AdmissionApplication, AdmissionCycle, AdmissionStatusHistory, Class
from app.models.students import normalize_guardian_contact
from app.services.admissions import EnrollmentError, enroll_application


ADMISSION_ROLES = ("Admin", "Head Teacher", "Head master", "Director of Studies", "Admissions Officer")
ALLOWED_TRANSITIONS = {
    "draft": {"submitted", "withdrawn"},
    "submitted": {"review", "withdrawn"},
    "review": {"shortlisted", "waitlisted", "rejected"},
    "shortlisted": {"assessment", "interview", "accepted", "waitlisted", "rejected"},
    "assessment": {"interview", "accepted", "waitlisted", "rejected"},
    "interview": {"accepted", "waitlisted", "rejected"},
    "waitlisted": {"accepted", "rejected", "withdrawn"},
    "accepted": {"enrolled", "withdrawn"},
}


def _public_rate_key(request, action):
    # REMOTE_ADDR is intentionally used instead of trusting a client-supplied forwarding header.
    return f"public-admissions:{action}:{request.META.get('REMOTE_ADDR') or 'unknown'}"


def _public_rate_limited(request, action, maximum):
    key = _public_rate_key(request, action)
    count = int(cache.get(key, 0))
    if count >= maximum:
        return True
    cache.set(key, count + 1, settings.PUBLIC_ADMISSION_RATE_SECONDS)
    return False


@feature_required("ADMISSIONS_ENABLED")
@feature_required("PUBLIC_ADMISSIONS_ENABLED")
@transaction.atomic
def public_admission_apply(request):
    if request.method == "POST" and _public_rate_limited(
        request, "apply", settings.PUBLIC_ADMISSION_MAX_SUBMISSIONS
    ):
        form = PublicAdmissionApplicationForm()
        form.add_error(None, "Too many applications were submitted from this connection. Please try again later.")
    else:
        form = PublicAdmissionApplicationForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            application = form.save(commit=False)
            application.status = AdmissionApplication.STATUS_SUBMITTED
            application.source = AdmissionApplication.SOURCE_PUBLIC
            application.privacy_consent_at = timezone.now()
            application.created_by = None
            application.save()
            AdmissionStatusHistory.objects.create(
                application=application, to_status=application.status,
                notes="Application submitted through the public admissions page.", changed_by=None,
            )
            return render(request, "admissions/public_success.html", {"application": application})
    return render(request, "admissions/public_apply.html", {
        "form": form, "has_open_cycles": form.fields["cycle"].queryset.exists(),
    })


@feature_required("ADMISSIONS_ENABLED")
@feature_required("PUBLIC_ADMISSIONS_ENABLED")
def public_admission_track(request):
    application = None
    form = PublicAdmissionTrackingForm(request.POST or None)
    if request.method == "POST":
        if _public_rate_limited(request, "track", settings.PUBLIC_ADMISSION_MAX_SUBMISSIONS * 4):
            form.add_error(None, "Too many tracking attempts. Please try again later.")
        elif form.is_valid():
            candidate = AdmissionApplication.objects.filter(
                application_number__iexact=form.cleaned_data["application_number"].strip(),
                source=AdmissionApplication.SOURCE_PUBLIC,
            ).first()
            if candidate and normalize_guardian_contact(candidate.contact) == normalize_guardian_contact(form.cleaned_data["contact"]):
                application = candidate
            else:
                form.add_error(None, "The application details could not be verified.")
    return render(request, "admissions/public_track.html", {"form": form, "application": application})


@feature_required("ADMISSIONS_ENABLED")
@role_required_any(*ADMISSION_ROLES)
def admission_dashboard(request):
    applications = AdmissionApplication.objects.select_related("cycle", "applying_class", "preferred_stream")
    counts = {value: applications.filter(status=value).count() for value, _ in AdmissionApplication.STATUS_CHOICES}
    pending_statuses = (
        AdmissionApplication.STATUS_SUBMITTED, AdmissionApplication.STATUS_REVIEW,
        AdmissionApplication.STATUS_SHORTLISTED, AdmissionApplication.STATUS_ASSESSMENT,
        AdmissionApplication.STATUS_INTERVIEW, AdmissionApplication.STATUS_WAITLISTED,
    )
    metrics = {
        "total": applications.count(),
        "review": counts.get(AdmissionApplication.STATUS_REVIEW, 0),
        "accepted": counts.get(AdmissionApplication.STATUS_ACCEPTED, 0),
        "pending": applications.filter(status__in=pending_statuses).count(),
        "enrolled": counts.get(AdmissionApplication.STATUS_ENROLLED, 0),
    }
    return render(request, "admissions/dashboard.html", {
        "applications": applications.order_by("-created_at")[:10], "counts": counts, "metrics": metrics,
    })


@feature_required("ADMISSIONS_ENABLED")
@role_required_any(*ADMISSION_ROLES)
def admission_list(request):
    applications = AdmissionApplication.objects.select_related("cycle", "applying_class", "preferred_stream").order_by("-created_at")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    cycle_id = request.GET.get("cycle", "").strip()
    class_id = request.GET.get("class_id", "").strip()
    date_from = parse_date(request.GET.get("date_from", ""))
    date_to = parse_date(request.GET.get("date_to", ""))
    if query:
        applications = applications.filter(
            Q(application_number__icontains=query) | Q(student_name__icontains=query)
            | Q(guardian__icontains=query) | Q(contact__icontains=query)
        )
    if status in dict(AdmissionApplication.STATUS_CHOICES):
        applications = applications.filter(status=status)
    if cycle_id.isdigit():
        applications = applications.filter(cycle_id=int(cycle_id))
    if class_id.isdigit():
        applications = applications.filter(applying_class_id=int(class_id))
    if date_from:
        applications = applications.filter(created_at__date__gte=date_from)
    if date_to:
        applications = applications.filter(created_at__date__lte=date_to)
    paginator = Paginator(applications, 25)
    page = paginator.get_page(request.GET.get("page", 1))
    return render(request, "admissions/list.html", {
        "applications": page, "statuses": AdmissionApplication.STATUS_CHOICES, "selected_status": status,
        "query": query, "selected_cycle": cycle_id, "selected_class": class_id,
        "date_from": request.GET.get("date_from", ""), "date_to": request.GET.get("date_to", ""),
        "cycles": AdmissionCycle.objects.order_by("-opens_on"), "classes": Class.objects.order_by("name"),
    })


@feature_required("ADMISSIONS_ENABLED")
@role_required_any(*ADMISSION_ROLES)
def admission_create(request):
    form = AdmissionApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        application = form.save(commit=False)
        application.created_by = request.user
        application.status = (
            AdmissionApplication.STATUS_SUBMITTED
            if request.POST.get("save_action") == "submit"
            else AdmissionApplication.STATUS_DRAFT
        )
        application.save()
        AdmissionStatusHistory.objects.create(application=application, to_status=application.status, changed_by=request.user)
        messages.success(request, f"Application {application.application_number} created.")
        return redirect("admission_detail", application_id=application.pk)
    return render(request, "admissions/form.html", {"form": form})


@feature_required("ADMISSIONS_ENABLED")
@role_required_any(*ADMISSION_ROLES)
def admission_detail(request, application_id):
    application = get_object_or_404(AdmissionApplication.objects.select_related("cycle", "applying_class", "preferred_stream", "enrolled_student"), pk=application_id)
    allowed = ALLOWED_TRANSITIONS.get(application.status, set())
    allowed_statuses = [(value, label) for value, label in AdmissionApplication.STATUS_CHOICES if value in allowed and value != "enrolled"]
    return render(request, "admissions/detail.html", {"application": application, "allowed_statuses": allowed_statuses})


@feature_required("ADMISSIONS_ENABLED")
@role_required_any(*ADMISSION_ROLES)
@transaction.atomic
def admission_change_status(request, application_id):
    application = get_object_or_404(AdmissionApplication.objects.select_for_update(), pk=application_id)
    if request.method != "POST":
        return redirect("admission_detail", application_id=application.pk)
    target = request.POST.get("status", "")
    if target == "enrolled" or target not in ALLOWED_TRANSITIONS.get(application.status, set()):
        messages.error(request, "That status transition is not allowed.")
    else:
        previous = application.status
        application.status = target
        application.decision_notes = request.POST.get("notes", "")[:2000]
        application.save(update_fields=("status", "decision_notes", "updated_at"))
        AdmissionStatusHistory.objects.create(
            application=application, from_status=previous, to_status=target,
            notes=application.decision_notes, changed_by=request.user,
        )
        messages.success(request, "Application status updated.")
    return redirect("admission_detail", application_id=application.pk)


@feature_required("ADMISSIONS_ENABLED")
@role_required_any("Admin", "Head Teacher", "Head master")
def admission_enroll(request, application_id):
    if request.method == "POST":
        try:
            student = enroll_application(application_id=application_id, actor=request.user)
            messages.success(request, f"Enrollment completed. Student number: {student.reg_no}.")
            return redirect("student_details_page", id=student.pk)
        except EnrollmentError as exc:
            messages.error(request, str(exc))
    return redirect("admission_detail", application_id=application_id)
