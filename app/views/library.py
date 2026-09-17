from datetime import timedelta
from decimal import Decimal, ROUND_UP

from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from app.decorators.decorators import role_required_any
from app.decorators.features import feature_required
from app.forms.library import LibraryBookForm, LibraryCopyForm, LibraryIssueForm, LibraryLostForm, LibraryReturnForm
from app.models import (
    LibraryBook, LibraryCategory, LibraryCopy, LibraryFine, LibraryLoan, LibraryPolicy, Staff, Student,
)
from app.services.library import CirculationError, issue_copy, mark_loan_lost, renew_loan, resolve_fine, return_loan


LIBRARY_ROLES = ("Admin", "Librarian", "Library Assistant", "Head Teacher", "Head master")


def _borrower_display(kind, borrower):
    if kind == "student":
        class_name = getattr(borrower.current_class, "code", "") or getattr(borrower.current_class, "name", "")
        stream = getattr(borrower.stream, "stream", "")
        class_label = " ".join(part for part in (class_name, stream) if part).strip()
        return {
            "name": borrower.student_name,
            "identifier": borrower.reg_no,
            "meta": " · ".join(part for part in ("Student", class_label, borrower.reg_no) if part),
        }
    staff_name = f"{borrower.first_name} {borrower.last_name}".strip()
    return {
        "name": staff_name,
        "identifier": f"STF-{borrower.pk:04d}",
        "meta": " · ".join(part for part in ("Staff", borrower.department, f"STF-{borrower.pk:04d}") if part),
    }


def _borrower_status_payload(kind, borrower):
    borrower_filter = {kind: borrower}
    active_loans = LibraryLoan.objects.filter(returned_at__isnull=True, **borrower_filter).select_related("copy__book")
    policy = LibraryPolicy.objects.filter(borrower_type=kind).first() or LibraryPolicy(borrower_type=kind)
    now = timezone.now()
    overdue_count = active_loans.filter(due_at__lt=now).count()
    outstanding_fine = LibraryFine.objects.filter(
        status=LibraryFine.STATUS_OUTSTANDING, **{f"loan__{kind}": borrower}
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
    active_count = active_loans.count()
    restrictions = []
    if active_count >= policy.maximum_books:
        restrictions.append("Borrowing limit reached")
    if policy.block_when_overdue and overdue_count:
        restrictions.append(f"{overdue_count} overdue item{'s' if overdue_count != 1 else ''}")
    if outstanding_fine > 0:
        restrictions.append("Outstanding library fine")
    due_at = now + timedelta(days=policy.loan_days)
    payload = _borrower_display(kind, borrower)
    payload.update({
        "kind": kind,
        "id": borrower.pk,
        "active_loans": active_count,
        "maximum_books": policy.maximum_books,
        "overdue_loans": overdue_count,
        "outstanding_fine": str(outstanding_fine.quantize(Decimal("0.01"))),
        "eligible": not restrictions,
        "eligibility_message": "; ".join(restrictions) if restrictions else "Eligible to borrow",
        "loan_days": policy.loan_days,
        "due_date": timezone.localtime(due_at).date().isoformat(),
        "due_label": timezone.localtime(due_at).strftime("%d %b %Y"),
        "recent_loans": [
            {
                "title": loan.copy.book.title,
                "copy": loan.copy.accession_number,
                "due": timezone.localtime(loan.due_at).strftime("%d %b %Y"),
                "overdue": loan.due_at < now,
            }
            for loan in active_loans.order_by("due_at")[:4]
        ],
    })
    return payload


def _loan_return_payload(loan):
    now = timezone.now()
    borrower_kind = "student" if loan.student_id else "staff"
    borrower = loan.student or loan.staff
    policy = LibraryPolicy.objects.filter(borrower_type=borrower_kind).first() or LibraryPolicy(borrower_type=borrower_kind)
    overdue_days = 0
    if now > loan.due_at:
        overdue_seconds = Decimal(str((now - loan.due_at).total_seconds()))
        overdue_days = int((overdue_seconds / Decimal("86400")).to_integral_value(rounding=ROUND_UP))
    fine = (Decimal(overdue_days) * policy.daily_fine).quantize(Decimal("0.01"))
    borrower_data = _borrower_display(borrower_kind, borrower)
    return {
        "id": loan.pk,
        "title": loan.copy.book.title,
        "author": loan.copy.book.author,
        "accession": loan.copy.accession_number,
        "barcode": loan.copy.barcode,
        "shelf": loan.copy.book.shelf_location,
        "borrower": borrower_data["name"],
        "borrower_meta": borrower_data["meta"],
        "issued": timezone.localtime(loan.issued_at).strftime("%d %b %Y"),
        "due": timezone.localtime(loan.due_at).strftime("%d %b %Y"),
        "overdue_days": overdue_days,
        "daily_fine": str(policy.daily_fine.quantize(Decimal("0.01"))),
        "calculated_fine": str(fine),
    }


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_dashboard(request):
    now = timezone.now()
    today = timezone.localdate()
    active_loans = LibraryLoan.objects.filter(returned_at__isnull=True)
    overdue_qs = active_loans.filter(due_at__lt=now).select_related("copy__book", "student", "staff")
    overdue_attention = list(overdue_qs.order_by("due_at")[:6])
    for loan in overdue_attention:
        loan.days_overdue = max(1, (today - timezone.localtime(loan.due_at).date()).days)
    activity = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        issued = LibraryLoan.objects.filter(issued_at__date=day).count()
        returned = LibraryLoan.objects.filter(returned_at__date=day).count()
        activity.append({"date": day, "issued": issued, "returned": returned})
    activity_peak = max([row["issued"] for row in activity] + [row["returned"] for row in activity] + [1])
    for row in activity:
        row["issued_height"] = max(4, round(row["issued"] * 100 / activity_peak))
        row["returned_height"] = max(4, round(row["returned"] * 100 / activity_peak))
    copies = LibraryCopy.objects.count()
    available = LibraryCopy.objects.filter(status=LibraryCopy.STATUS_AVAILABLE).count()
    context = {
        "titles": LibraryBook.objects.count(), "copies": copies, "available": available,
        "availability_percent": round((available / copies) * 100) if copies else 0,
        "active_loans": active_loans.count(), "overdue": overdue_qs.count(),
        "due_today": active_loans.filter(due_at__date=today).count(),
        "issued_today": LibraryLoan.objects.filter(issued_at__date=today).count(),
        "returned_today": LibraryLoan.objects.filter(returned_at__date=today).count(),
        "outstanding_fines": LibraryFine.objects.filter(status=LibraryFine.STATUS_OUTSTANDING).count(),
        "overdue_attention": overdue_attention, "activity": activity,
        "popular_books": LibraryBook.objects.annotate(issue_count=Count("copies__loans")).filter(
            issue_count__gt=0
        ).order_by("-issue_count", "title")[:5],
        "today": today,
    }
    return render(request, "library/dashboard.html", context)


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_catalogue(request):
    books = LibraryBook.objects.select_related("category").annotate(
        copy_count=Count("copies", distinct=True),
        available_count=Count("copies", filter=Q(copies__status="available"), distinct=True),
    )
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    availability = request.GET.get("availability", "").strip()
    if query:
        books = books.filter(
            Q(title__icontains=query) | Q(isbn__icontains=query) | Q(author__icontains=query)
            | Q(copies__barcode__icontains=query) | Q(copies__accession_number__icontains=query)
        ).distinct()
    if category.isdigit():
        books = books.filter(category_id=int(category))
    if availability == "available":
        books = books.filter(available_count__gt=0)
    elif availability == "unavailable":
        books = books.filter(available_count=0)
    return render(request, "library/catalogue.html", {
        "books": books.order_by("title"), "query": query, "categories": LibraryCategory.objects.order_by("name"),
        "selected_category": category, "selected_availability": availability,
    })


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_book_create(request):
    form = LibraryBookForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        book = form.save()
        messages.success(request, "Book title added.")
        return redirect("library_book_detail", book_id=book.pk)
    return render(request, "library/form.html", {"form": form, "title": "Add book title"})


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_book_detail(request, book_id):
    book = get_object_or_404(LibraryBook.objects.prefetch_related("copies"), pk=book_id)
    copies = book.copies.all()
    history = LibraryLoan.objects.filter(copy__book=book).select_related("copy", "student", "staff").order_by("-issued_at")[:10]
    return render(request, "library/book_detail.html", {
        "book": book, "copy_count": copies.count(),
        "available_count": copies.filter(status=LibraryCopy.STATUS_AVAILABLE).count(),
        "issued_count": copies.filter(status=LibraryCopy.STATUS_ON_LOAN).count(), "history": history,
    })


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_copy_create(request, book_id):
    book = get_object_or_404(LibraryBook, pk=book_id)
    form = LibraryCopyForm(request.POST or None, initial={"book": book})
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Physical copy added.")
        return redirect("library_book_detail", book_id=book.pk)
    return render(request, "library/form.html", {"form": form, "title": f"Add copy — {book.title}"})


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_issue(request):
    form = LibraryIssueForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            student = form.cleaned_data.get("student")
            staff = form.cleaned_data.get("staff")
            loan = issue_copy(
                copy_id=form.cleaned_data["copy"].pk, actor=request.user,
                student_id=student.pk if student else None, staff_id=staff.pk if staff else None,
            )
            messages.success(request, f"Issued until {loan.due_at:%d %b %Y}.")
            return redirect(f'{reverse("library_issue")}?issued={loan.pk}')
        except (CirculationError, Student.DoesNotExist, Staff.DoesNotExist) as exc:
            form.add_error(None, str(exc))
    issued_loan = None
    issued_id = request.GET.get("issued", "")
    if issued_id.isdigit():
        issued_loan = LibraryLoan.objects.select_related(
            "copy__book", "student__current_class", "student__stream", "staff"
        ).filter(pk=int(issued_id)).first()
    return render(request, "library/issue.html", {
        "form": form,
        "issued_loan": issued_loan,
        "initial_borrower_kind": "student" if request.POST.get("student") else "staff" if request.POST.get("staff") else "",
        "initial_borrower_id": request.POST.get("student") or request.POST.get("staff") or "",
        "initial_copy_id": request.POST.get("copy", ""),
    })


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_borrower_lookup(request):
    kind = request.GET.get("kind", "").strip().lower()
    borrower_id = request.GET.get("id", "").strip()
    if kind in {"student", "staff"} and borrower_id.isdigit():
        if kind == "student":
            borrower = get_object_or_404(
                Student.objects.select_related("current_class", "stream"), pk=int(borrower_id), is_active=True,
            )
        else:
            borrower = get_object_or_404(Staff, pk=int(borrower_id), staff_status="Active")
        return JsonResponse({"borrower": _borrower_status_payload(kind, borrower)})

    query = request.GET.get("q", "").strip()
    selected_filter = request.GET.get("filter", "all").strip().lower()
    if not query:
        return JsonResponse({"results": []})
    results = []
    if selected_filter in {"all", "students"}:
        student_query = (
            Q(student_name__icontains=query) | Q(reg_no__icontains=query)
            | Q(contact__icontains=query)
        )
        if query.isdigit():
            student_query |= Q(pk=int(query))
        students = Student.objects.filter(student_query, is_active=True).select_related(
            "current_class", "stream"
        ).order_by("student_name")[:8]
        for student in students:
            item = _borrower_display("student", student)
            item.update({"kind": "student", "id": student.pk, "exact": query.casefold() == student.reg_no.casefold()})
            results.append(item)
    if selected_filter in {"all", "staff"}:
        staff_query = (
            Q(first_name__icontains=query) | Q(last_name__icontains=query)
            | Q(contacts__icontains=query) | Q(nin_no__icontains=query)
        )
        if query.isdigit():
            staff_query |= Q(pk=int(query))
        virtual_staff_id = query.removeprefix("STF-").removeprefix("stf-")
        if virtual_staff_id.isdigit():
            staff_query |= Q(pk=int(virtual_staff_id))
        staff_members = Staff.objects.filter(staff_query, staff_status="Active").order_by(
            "first_name", "last_name"
        )[:8]
        for staff in staff_members:
            item = _borrower_display("staff", staff)
            item.update({
                "kind": "staff", "id": staff.pk,
                "exact": query.casefold() in {str(staff.pk).casefold(), f"stf-{staff.pk:04d}".casefold()},
            })
            results.append(item)
    results.sort(key=lambda item: (not item["exact"], item["name"].casefold()))
    return JsonResponse({"results": results[:10]})


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_copy_lookup(request):
    copy_id = request.GET.get("id", "").strip()
    query = request.GET.get("q", "").strip()
    copies = LibraryCopy.objects.filter(status=LibraryCopy.STATUS_AVAILABLE).select_related("book")
    if copy_id.isdigit():
        copies = copies.filter(pk=int(copy_id))
    elif query:
        copies = copies.filter(
            Q(barcode__icontains=query) | Q(accession_number__icontains=query)
            | Q(book__title__icontains=query) | Q(book__isbn__icontains=query)
            | Q(book__author__icontains=query)
        )
    else:
        return JsonResponse({"results": []})
    matched = list(copies.order_by("book__title", "accession_number")[:12])
    available_by_book = {
        row["book_id"]: row["total"]
        for row in LibraryCopy.objects.filter(
            status=LibraryCopy.STATUS_AVAILABLE, book_id__in={copy.book_id for copy in matched}
        ).values("book_id").annotate(total=Count("id"))
    }
    results = []
    for copy in matched:
        results.append({
            "id": copy.pk,
            "title": copy.book.title,
            "author": copy.book.author,
            "isbn": copy.book.isbn,
            "accession": copy.accession_number,
            "barcode": copy.barcode,
            "shelf": copy.book.shelf_location,
            "condition": copy.condition_notes or "Good",
            "available_copies": available_by_book.get(copy.book_id, 0),
            "exact": bool(query) and query.casefold() in {copy.barcode.casefold(), copy.accession_number.casefold()},
        })
    results.sort(key=lambda item: (not item["exact"], item["title"].casefold(), item["accession"].casefold()))
    return JsonResponse({"results": results})


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_active_loan_lookup(request):
    query = request.GET.get("q", "").strip()
    loan_id = request.GET.get("id", "").strip()
    loans = LibraryLoan.objects.filter(returned_at__isnull=True).select_related(
        "copy__book", "student__current_class", "student__stream", "staff",
    )
    if loan_id.isdigit():
        loans = loans.filter(pk=int(loan_id))
    elif query:
        loans = loans.filter(
            Q(copy__barcode__icontains=query) | Q(copy__accession_number__icontains=query)
            | Q(copy__book__title__icontains=query) | Q(copy__book__isbn__icontains=query)
            | Q(student__student_name__icontains=query) | Q(student__reg_no__icontains=query)
            | Q(staff__first_name__icontains=query) | Q(staff__last_name__icontains=query)
        )
    else:
        return JsonResponse({"results": []})
    results = []
    for loan in loans.order_by("due_at")[:12]:
        item = _loan_return_payload(loan)
        item["exact"] = bool(query) and query.casefold() in {
            loan.copy.barcode.casefold(), loan.copy.accession_number.casefold(),
        }
        results.append(item)
    results.sort(key=lambda item: not item["exact"])
    return JsonResponse({"results": results})


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_return_station(request):
    form = LibraryReturnForm(request.POST or None)
    if request.method == "POST":
        loan_id = request.POST.get("loan", "")
        if not loan_id.isdigit():
            form.add_error(None, "Scan or select an active loan before confirming the return.")
        elif form.is_valid():
            try:
                loan = return_loan(
                    loan_id=int(loan_id), actor=request.user, condition=form.cleaned_data["condition"],
                    damage_amount=form.cleaned_data.get("damage_amount") or 0,
                    notes=form.cleaned_data.get("notes", ""),
                )
                messages.success(request, "Book returned and any applicable library fine was recorded.")
                return redirect(f'{reverse("library_return_station")}?returned={loan.pk}')
            except (CirculationError, LibraryLoan.DoesNotExist) as exc:
                form.add_error(None, str(exc))
    returned_loan = None
    returned_id = request.GET.get("returned", "")
    if returned_id.isdigit():
        returned_loan = LibraryLoan.objects.select_related(
            "copy__book", "student__current_class", "student__stream", "staff"
        ).prefetch_related("fines").filter(pk=int(returned_id), returned_at__isnull=False).first()
    return render(request, "library/return.html", {
        "form": form,
        "returned_loan": returned_loan,
        "initial_loan_id": request.POST.get("loan", ""),
    })


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_loans(request):
    loans = LibraryLoan.objects.select_related("copy__book", "student", "staff").filter(returned_at__isnull=True)
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "active")
    if query:
        loans = loans.filter(
            Q(copy__barcode__icontains=query) | Q(copy__accession_number__icontains=query)
            | Q(copy__book__title__icontains=query) | Q(student__student_name__icontains=query)
            | Q(student__reg_no__icontains=query) | Q(staff__first_name__icontains=query)
            | Q(staff__last_name__icontains=query)
        )
    if status == "overdue":
        loans = loans.filter(due_at__lt=timezone.now())
    elif status == "due_today":
        loans = loans.filter(due_at__date=timezone.localdate())
    return render(request, "library/loans.html", {
        "loans": loans.order_by("due_at"), "now": timezone.now(), "query": query, "selected_status": status,
    })


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_members(request):
    query = request.GET.get("q", "").strip()
    students = Student.objects.filter(is_active=True).select_related("current_class", "stream").annotate(
        active_loan_count=Count("library_loans", filter=Q(library_loans__returned_at__isnull=True), distinct=True),
        overdue_count=Count("library_loans", filter=Q(library_loans__returned_at__isnull=True, library_loans__due_at__lt=timezone.now()), distinct=True),
    )
    staff = Staff.objects.filter(staff_status="Active").annotate(
        active_loan_count=Count("library_loans", filter=Q(library_loans__returned_at__isnull=True), distinct=True),
        overdue_count=Count("library_loans", filter=Q(library_loans__returned_at__isnull=True, library_loans__due_at__lt=timezone.now()), distinct=True),
    )
    if query:
        students = students.filter(Q(student_name__icontains=query) | Q(reg_no__icontains=query) | Q(contact__icontains=query))
        staff = staff.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(contacts__icontains=query))
    return render(request, "library/members.html", {
        "students": students.order_by("student_name")[:100], "staff_members": staff.order_by("first_name", "last_name")[:100],
        "query": query,
    })


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_return(request, loan_id):
    if request.method == "POST":
        form = LibraryReturnForm(request.POST)
        if form.is_valid():
            try:
                return_loan(
                    loan_id=loan_id, actor=request.user, condition=form.cleaned_data["condition"],
                    damage_amount=form.cleaned_data.get("damage_amount") or 0, notes=form.cleaned_data.get("notes", ""),
                )
                messages.success(request, "Book returned and any applicable library fine was recorded.")
            except (CirculationError, LibraryLoan.DoesNotExist) as exc:
                messages.error(request, str(exc))
        else:
            messages.error(request, "Return not recorded: " + " ".join(error for errors in form.errors.values() for error in errors))
    return redirect("library_loans")


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_renew(request, loan_id):
    if request.method == "POST":
        try:
            renew_loan(loan_id=loan_id, actor=request.user)
            messages.success(request, "Loan renewed.")
        except CirculationError as exc:
            messages.error(request, str(exc))
    return redirect("library_loans")


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_mark_lost(request, loan_id):
    if request.method == "POST":
        form = LibraryLostForm(request.POST)
        if form.is_valid():
            try:
                mark_loan_lost(
                    loan_id=loan_id, actor=request.user, amount=form.cleaned_data["amount"],
                    notes=form.cleaned_data.get("notes", ""),
                )
                messages.success(request, "The copy was marked lost and the library charge recorded.")
            except (CirculationError, LibraryLoan.DoesNotExist) as exc:
                messages.error(request, str(exc))
        else:
            messages.error(request, "Lost-item action not recorded. Enter a valid non-negative replacement charge.")
    return redirect("library_loans")


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_fines(request):
    fines = LibraryFine.objects.select_related(
        "loan__copy__book", "loan__student", "loan__staff", "assessed_by", "resolved_by"
    )
    status = request.GET.get("status", "outstanding")
    if status in dict(LibraryFine.STATUS_CHOICES):
        fines = fines.filter(status=status)
    return render(request, "library/fines.html", {"fines": fines, "selected_status": status})


@feature_required("LIBRARY_ENABLED")
@role_required_any(*LIBRARY_ROLES)
def library_fine_resolve(request, fine_id):
    if request.method == "POST":
        try:
            resolve_fine(fine_id=fine_id, actor=request.user, resolution=request.POST.get("resolution", ""))
            messages.success(request, "Library fine updated.")
        except (CirculationError, LibraryFine.DoesNotExist) as exc:
            messages.error(request, str(exc))
    return redirect("library_fines")
