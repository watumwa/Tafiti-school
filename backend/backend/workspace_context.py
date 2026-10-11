"""Workspace-context facade with user-facing display enrichments.

The full workspace builders live in ``workspace_context_impl``.  This facade
re-exports the existing API and adds presentation-only bill labels so views can
show meaningful charge names instead of database record numbers.
"""

from . import workspace_context_impl as _impl

# Preserve the complete public/private module surface because workspace.py also
# imports helpers such as _entity_path and _module_path from this module.
for _name, _value in vars(_impl).items():
    if _name not in {
        "__name__",
        "__file__",
        "__package__",
        "__spec__",
        "__loader__",
        "__builtins__",
    }:
        globals()[_name] = _value


def _parse_bill_reference(value):
    text = str(value or "").strip()
    if not text.startswith("Bill #"):
        return None
    try:
        return int(text.removeprefix("Bill #").strip())
    except (TypeError, ValueError):
        return None


def _bill_display_name(bill):
    names = []
    for item in bill.items.all():
        bill_item = getattr(item, "bill_item", None)
        name = str(getattr(bill_item, "item_name", "") or item.description or "").strip()
        if name and name not in names:
            names.append(name)
    return " · ".join(names) if names else f"Bill #{bill.pk}"


def _replace_bill_numbers_with_names(payload):
    references = []
    for tab in payload.get("tabs", []):
        for row in tab.get("rows", []):
            for field in ("bill", "reference"):
                bill_id = _parse_bill_reference(row.get(field))
                if bill_id is not None:
                    references.append((row, field, bill_id))

    if not references:
        return payload

    bill_ids = {bill_id for _, _, bill_id in references}
    bills = StudentBill.objects.filter(pk__in=bill_ids).prefetch_related("items__bill_item")
    labels = {bill.pk: _bill_display_name(bill) for bill in bills}
    for row, field, bill_id in references:
        if bill_id in labels:
            row[field] = labels[bill_id]
    return payload


def build_entity_workspace(request, resource: str, pk: int):
    payload = _impl.build_entity_workspace(request, resource, pk)
    if resource in {"students", "fees"}:
        return _replace_bill_numbers_with_names(payload)
    return payload


del _name, _value
