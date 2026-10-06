from __future__ import annotations

import csv
from html import escape
from io import StringIO

from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response

from .workspace import RESOURCE_BUILDERS, WorkspaceBaseAPIView, _can_access, _search


EXPORTABLE_RESOURCES = {
    "students", "staff", "admissions", "parents", "classes", "subjects", "results",
    "attendance", "timetable", "fees", "fees-payments", "fees-class-bills", "fees-bill-items",
    "finance", "finance-budgets", "finance-budget-items", "finance-expenditure-items",
    "finance-expenses", "finance-vendors", "finance-income", "library", "communication", "audit",
}


def _export_payload(request, resource: str):
    builder = RESOURCE_BUILDERS.get(resource)
    if not builder or resource not in EXPORTABLE_RESOURCES:
        raise KeyError(resource)
    if not _can_access(request, resource):
        raise PermissionError("Your current role does not have access to this report.")
    payload = builder(request)
    columns = payload.get("columns", [])
    rows = _search(payload.get("rows", []), request.query_params.get("q", ""))
    return payload.get("title", resource.replace("-", " ").title()), columns, rows


def _csv_response(resource: str, title: str, columns, rows):
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for _key, label in columns])
    for row in rows:
        writer.writerow([row.get(key, "") for key, _label in columns])
    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="tafiti-{resource}.csv"'
    response["X-Tafiti-Report-Title"] = title
    return response


def _html_response(title: str, columns, rows):
    head = "".join(f"<th>{escape(str(label))}</th>" for _key, label in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(row.get(key, '') or ''))}</td>" for key, _label in columns) + "</tr>"
        for row in rows
    )
    document = f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><title>{escape(title)}</title>
<style>body{{font-family:Arial,sans-serif;margin:28px;color:#172033}}h1{{font-size:20px;margin:0 0 6px}}p{{font-size:11px;color:#64748b;margin:0 0 18px}}table{{width:100%;border-collapse:collapse;font-size:10px}}th,td{{border:1px solid #dbe3ef;padding:7px;text-align:left;vertical-align:top}}th{{background:#f3f7fc}}@media print{{body{{margin:8mm}}button{{display:none}}}}</style></head>
<body><button onclick=\"window.print()\">Print</button><h1>{escape(title)}</h1><p>Generated from the permission-scoped Tafiti workspace.</p><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></body></html>"""
    return HttpResponse(document, content_type="text/html; charset=utf-8")


class WorkspaceExportAPIView(WorkspaceBaseAPIView):
    def get(self, request, resource: str):
        try:
            title, columns, rows = _export_payload(request, resource)
        except KeyError:
            return Response({"detail": "This workspace report is not exportable."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        format_name = str(request.query_params.get("format") or "csv").strip().lower()
        if format_name == "csv":
            return _csv_response(resource, title, columns, rows)
        if format_name == "print":
            return _html_response(title, columns, rows)
        return Response({"detail": "Supported export formats are csv and print."}, status=status.HTTP_400_BAD_REQUEST)
