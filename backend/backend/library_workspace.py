from __future__ import annotations

from decimal import Decimal
from typing import Any

from django import forms
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.response import Response

from app.forms.library import LibraryBookForm, LibraryIssueForm, LibraryLostForm, LibraryReturnForm
from app.models import LibraryBook, LibraryCopy, LibraryFine, LibraryLoan, Staff, Student, StudentBillItem
from app.services.library import (
    CirculationError,
    issue_copy,
    mark_loan_lost,
    renew_loan,
    resolve_fine,
    return_loan,
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


READ_ROLES = {"Admin", "Head Teacher", "Librarian", "Library Assistant"}
WRITE_ROLES = {"Admin", "Librarian", "Library Assistant"}


def _role(request) -> str:
    return canonical_role_label(resolve_active_role(request.user, _token_context(request)).label)


def _can_read(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in READ_ROLES)


def _can_write(request) -> bool:
    return bool(request.user.is_superuser or _role(request) in WRITE_ROLES)


def _schema(form: forms.Form, *, title: str, submit_label: str, resource: str) -> dict[str, Any]:
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
        "mode": "create",
        "title": title,
        "submit_label": submit_label,
        "fields": fields,
        "actions": {
            "view": True,
            "create": True,
            "edit": True,
            "delete": False,
            "create_label": submit_label,
            "edit_label": "Edit",
            "delete_label": "Delete",
        },
    }


def _money(value) -> str:
    return f"{Decimal(value or 0):,.0f}"


def _loan_row(loan: LibraryLoan) -> dict[str, Any]:
    status_label = "Returned" if loan.returned_at else ("Overdue" if loan.is_overdue else "On loan")
    return {
        "id": loan.pk,
        "book": loan.copy.book.title,
        "accession": loan.copy.accession_number,
        "borrower": str(loan.borrower),
        "borrower_type": "Student" if loan.student_id else "Staff",
        "issued": loan.issued_at.isoformat(),
        "due": loan.due_at.isoformat(),
        "returned": loan.returned_at.isoformat() if loan.returned_at else "",
        "renewals": loan.renewals,
        "status": status_label,
    }


def _book_rows():
    rows = []
    for book in LibraryBook.objects.select_related("category").prefetch_related("copies").order_by("title")[:1500]:
        copies = list(book.copies.all())
        rows.append({
            "id": book.pk,
            "title": book.title,
            "author": book.author or "—",
            "isbn": book.isbn or "—",
            "category": str(book.category or "—"),
            "shelf": book.shelf_location or "—",
            "copies": len(copies),
            "available": sum(copy.status == LibraryCopy.STATUS_AVAILABLE for copy in copies),
            "on_loan": sum(copy.status == LibraryCopy.STATUS_ON_LOAN for copy in copies),
        })
    return rows


def _fine_rows():
    queryset = LibraryFine.objects.select_related(
        "loan__copy__book", "loan__student", "loan__staff"
    ).order_by("-assessed_at")[:1500]
    fines = list(queryset)
    ledger_keys = set(StudentBillItem.objects.filter(
        notes__in=[f"library-fine:{fine.pk}" for fine in fines],
    ).values_list("notes", flat=True))
    return [
        {
            "id": fine.pk,
            "book": fine.loan.copy.book.title,
            "borrower": str(fine.loan.borrower),
            "reason": fine.get_reason_display(),
            "amount": _money(fine.amount),
            "status": fine.get_status_display(),
            "assessed": fine.assessed_at.isoformat(),
            "notes": fine.notes or "—",
            "billed": f"library-fine:{fine.pk}" in ledger_keys,
        }
        for fine in fines
    ]


class LibraryConsoleAPIView(WorkspaceBaseAPIView):
    def _permission(self, request, *, write=False):
        allowed = _can_write(request) if write else _can_read(request)
        if allowed:
            return None
        return Response(
            {"detail": "Your current role cannot manage the library." if write else "Your current role cannot access the library."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def get(self, request, screen: str, pk: int | None = None):
        failure = self._permission(request)
        if failure:
            return failure

        if screen == "overview":
            loans = LibraryLoan.objects.select_related("copy__book", "student", "staff")
            active = loans.filter(returned_at__isnull=True)
            overdue = [loan for loan in active if loan.is_overdue]
            return Response({
                "books": LibraryBook.objects.count(),
                "copies": LibraryCopy.objects.count(),
                "available": LibraryCopy.objects.filter(status=LibraryCopy.STATUS_AVAILABLE).count(),
                "on_loan": active.count(),
                "overdue": len(overdue),
                "outstanding_fines": LibraryFine.objects.filter(status=LibraryFine.STATUS_OUTSTANDING).count(),
                "student_members": Student.objects.filter(is_active=True).count(),
                "staff_members": Staff.objects.filter(staff_status="Active").count(),
            })

        if screen == "books":
            if pk is not None:
                try:
                    book = LibraryBook.objects.get(pk=pk)
                except LibraryBook.DoesNotExist:
                    return Response({"detail": "Book not found."}, status=status.HTTP_404_NOT_FOUND)
                form = LibraryBookForm(instance=book)
                payload = _schema(form, title="Edit book", submit_label="Save changes", resource="library-book")
                payload["mode"] = "edit"
                return Response(payload)
            return Response({
                "rows": _book_rows(),
                "form": _schema(LibraryBookForm(), title="Add book", submit_label="Add book", resource="library-book"),
                "can_write": _can_write(request),
            })

        if screen == "loans":
            queryset = LibraryLoan.objects.select_related("copy__book", "student", "staff").order_by("-issued_at")[:1500]
            return Response({"rows": [_loan_row(loan) for loan in queryset], "can_write": _can_write(request)})

        if screen == "fines":
            return Response({"rows": _fine_rows(), "can_write": _can_write(request)})

        if screen == "issue":
            return Response(_schema(LibraryIssueForm(), title="Issue book", submit_label="Issue book", resource="library-issue"))

        if screen == "return":
            if pk is None:
                return Response({"detail": "Choose a loan to return."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                loan = LibraryLoan.objects.get(pk=pk)
            except LibraryLoan.DoesNotExist:
                return Response({"detail": "Loan not found."}, status=status.HTTP_404_NOT_FOUND)
            if loan.returned_at:
                return Response({"detail": "This loan is already closed."}, status=status.HTTP_409_CONFLICT)
            return Response(_schema(LibraryReturnForm(), title="Return book", submit_label="Complete return", resource="library-return"))

        if screen == "lost":
            if pk is None:
                return Response({"detail": "Choose a loan first."}, status=status.HTTP_400_BAD_REQUEST)
            return Response(_schema(LibraryLostForm(), title="Mark item lost", submit_label="Mark lost", resource="library-lost"))

        return Response({"detail": "Library workspace not found."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, screen: str, pk: int | None = None):
        failure = self._permission(request, write=True)
        if failure:
            return failure

        if screen == "books":
            instance = None
            if pk is not None:
                try:
                    instance = LibraryBook.objects.get(pk=pk)
                except LibraryBook.DoesNotExist:
                    return Response({"detail": "Book not found."}, status=status.HTTP_404_NOT_FOUND)
            payload = request.data if hasattr(request.data, "getlist") else _payload_to_querydict(dict(request.data))
            form = LibraryBookForm(payload, instance=instance)
            if not form.is_valid():
                return Response({"detail": "Check the highlighted fields.", "errors": _form_errors(form)}, status=status.HTTP_400_BAD_REQUEST)
            try:
                with transaction.atomic():
                    book = form.save()
            except IntegrityError:
                return Response({"detail": "That book conflicts with an existing catalogue record."}, status=status.HTTP_409_CONFLICT)
            return Response({"detail": "Book saved successfully.", "id": book.pk}, status=status.HTTP_200_OK if instance else status.HTTP_201_CREATED)

        if screen == "issue":
            payload = request.data if hasattr(request.data, "getlist") else _payload_to_querydict(dict(request.data))
            form = LibraryIssueForm(payload)
            if not form.is_valid():
                return Response({"detail": "Check the borrower and copy selection.", "errors": _form_errors(form)}, status=status.HTTP_400_BAD_REQUEST)
            try:
                loan = issue_copy(
                    copy_id=form.cleaned_data["copy"].pk,
                    actor=request.user,
                    student_id=getattr(form.cleaned_data.get("student"), "pk", None),
                    staff_id=getattr(form.cleaned_data.get("staff"), "pk", None),
                )
            except (CirculationError, LibraryCopy.DoesNotExist, Student.DoesNotExist, Staff.DoesNotExist) as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
            return Response({"detail": "Book issued successfully.", "id": loan.pk}, status=status.HTTP_201_CREATED)

        if screen == "renew":
            if pk is None:
                return Response({"detail": "Choose a loan first."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                loan = renew_loan(loan_id=pk, actor=request.user)
            except (CirculationError, LibraryLoan.DoesNotExist) as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
            return Response({"detail": "Loan renewed successfully.", "due": loan.due_at.isoformat(), "renewals": loan.renewals})

        if screen == "return":
            if pk is None:
                return Response({"detail": "Choose a loan first."}, status=status.HTTP_400_BAD_REQUEST)
            payload = request.data if hasattr(request.data, "getlist") else _payload_to_querydict(dict(request.data))
            form = LibraryReturnForm(payload)
            if not form.is_valid():
                return Response({"detail": "Check the return details.", "errors": _form_errors(form)}, status=status.HTTP_400_BAD_REQUEST)
            try:
                loan = return_loan(
                    loan_id=pk,
                    actor=request.user,
                    condition=form.cleaned_data["condition"],
                    damage_amount=form.cleaned_data.get("damage_amount") or 0,
                    notes=form.cleaned_data.get("notes") or "",
                )
            except (CirculationError, LibraryLoan.DoesNotExist) as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
            fine_count = loan.fines.count()
            return Response({
                "detail": (
                    f"Book returned successfully. {fine_count} library charge(s) were added to the student fee ledger."
                    if loan.student_id and fine_count
                    else "Book returned successfully."
                ),
                "returned": loan.returned_at.isoformat() if loan.returned_at else "",
            })

        if screen == "lost":
            if pk is None:
                return Response({"detail": "Choose a loan first."}, status=status.HTTP_400_BAD_REQUEST)
            payload = request.data if hasattr(request.data, "getlist") else _payload_to_querydict(dict(request.data))
            form = LibraryLostForm(payload)
            if not form.is_valid():
                return Response({"detail": "Check the lost-item details.", "errors": _form_errors(form)}, status=status.HTTP_400_BAD_REQUEST)
            try:
                mark_loan_lost(
                    loan_id=pk,
                    actor=request.user,
                    amount=form.cleaned_data["amount"],
                    notes=form.cleaned_data.get("notes") or "",
                )
            except (CirculationError, LibraryLoan.DoesNotExist) as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
            return Response({
                "detail": (
                    "The item was marked lost and its replacement charge was added to the student fee ledger."
                    if LibraryLoan.objects.filter(pk=pk, student__isnull=False).exists()
                    else "The item was marked lost and the replacement charge was assessed."
                )
            })

        if screen == "fine":
            if pk is None:
                return Response({"detail": "Choose a fine first."}, status=status.HTTP_400_BAD_REQUEST)
            resolution = str(request.data.get("resolution") or "").strip().lower()
            try:
                fine = resolve_fine(fine_id=pk, actor=request.user, resolution=resolution)
            except (CirculationError, LibraryFine.DoesNotExist) as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
            return Response({"detail": f"Fine marked {fine.get_status_display().lower()}.", "status": fine.status})

        return Response({"detail": "Library action not found."}, status=status.HTTP_404_NOT_FOUND)
