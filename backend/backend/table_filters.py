from __future__ import annotations

from datetime import date, datetime
from typing import Any


FILTER_PREFIX = "filter_"
SKIP_FILTER_KEYS = {
    "id", "photo", "description", "address", "contact", "email", "guardian", "path",
    "object", "approved_by", "recorded_by", "borrower", "student", "name", "title",
    "application", "book", "reference",
}
DATE_HINTS = ("date", "time", "updated", "issued", "due", "returned", "when")


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_date_key(key: str) -> bool:
    normalized = key.casefold()
    return any(hint in normalized for hint in DATE_HINTS)


def _date_value(value: Any):
    if value in (None, "", "—"):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def build_table_meta(columns: list[list[str]] | list[tuple[str, str]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    filter_options: dict[str, list[dict[str, str]]] = {}
    date_columns: list[dict[str, str]] = []

    for key, label in columns:
        if _is_date_key(key):
            date_columns.append({"key": key, "label": label})
            continue
        if key in SKIP_FILTER_KEYS:
            continue

        values = sorted(
            {_text(row.get(key)) for row in rows if _text(row.get(key)) not in {"", "—"}},
            key=str.casefold,
        )
        if 1 < len(values) <= 35:
            filter_options[key] = [{"value": value, "label": value} for value in values]

    return {
        "filter_options": filter_options,
        "date_columns": date_columns,
    }


def apply_table_filters(request, rows: list[dict[str, Any]], columns: list[list[str]] | list[tuple[str, str]]) -> list[dict[str, Any]]:
    filtered = rows
    column_keys = {key for key, _label in columns}

    for key in column_keys:
        requested = request.query_params.get(f"{FILTER_PREFIX}{key}", "").strip()
        if not requested:
            continue
        target = requested.casefold()
        filtered = [row for row in filtered if _text(row.get(key)).casefold() == target]

    date_key = request.query_params.get("date_key", "").strip()
    if date_key not in column_keys or not _is_date_key(date_key):
        date_key = ""

    date_from = _date_value(request.query_params.get("date_from"))
    date_to = _date_value(request.query_params.get("date_to"))
    if date_key and (date_from or date_to):
        next_rows = []
        for row in filtered:
            value = _date_value(row.get(date_key))
            if not value:
                continue
            if date_from and value < date_from:
                continue
            if date_to and value > date_to:
                continue
            next_rows.append(row)
        filtered = next_rows

    return filtered
