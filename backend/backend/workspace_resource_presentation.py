from __future__ import annotations

from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.response import Response

from app.models import ClassBill

from .workspace import (
    RESOURCE_BUILDERS,
    WorkspaceResourceAPIView,
    _can_access,
    _paginate,
    _search,
    record_finance_access_denial,
)
from .workspace_forms import resource_action_policy


class WorkspaceResourcePresentationAPIView(WorkspaceResourceAPIView):
    """Add small presentation enrichments without changing core resource builders."""

    def get(self, request, resource: str):
        if resource != "fees-class-bills":
            return super().get(request, resource)

        builder = RESOURCE_BUILDERS.get(resource)
        if not builder:
            return Response({"detail": "Unknown workspace resource."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access(request, resource):
            record_finance_access_denial(request, resource, operation="list")
            return Response(
                {
                    "code": "resource_forbidden",
                    "detail": "Your current role does not have access to this workspace module.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            payload = builder(request)
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        rows = payload.pop("rows")
        policy_ids = [row.get("id") for row in rows if row.get("id")]
        policies = ClassBill.objects.filter(pk__in=policy_ids)
        policy_labels = {}
        for policy in policies:
            label = policy.get_applies_to_display()
            if policy.applies_to == ClassBill.APPLIES_ALL:
                label = "All students (fallback)"
            policy_labels[policy.pk] = label

        for row in rows:
            row["applies_to"] = policy_labels.get(row.get("id"), "—")
            try:
                row["amount"] = f"{Decimal(str(row.get('amount') or 0)):,.0f}"
            except (InvalidOperation, TypeError, ValueError):
                pass

        columns = list(payload.get("columns") or [])
        if not any(key == "applies_to" for key, _ in columns):
            amount_index = next((index for index, (key, _) in enumerate(columns) if key == "amount"), len(columns))
            columns.insert(amount_index, ["applies_to", "Who pays"])
        payload["columns"] = columns
        payload["description"] = (
            "Fee rules for each academic class. Day or Boarding rules automatically override "
            "the All students fallback for matching learners."
        )

        rows = _search(rows, request.query_params.get("q", ""))
        page = _paginate(request, rows)
        return Response(
            {
                "resource": resource,
                **payload,
                "columns": [{"key": key, "label": label} for key, label in payload["columns"]],
                "actions": resource_action_policy(request, resource),
                **page,
            }
        )
