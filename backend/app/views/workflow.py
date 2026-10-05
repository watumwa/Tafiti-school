from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from app.services.workflow_readiness import readiness_for_request


@login_required
def workflow_readiness_view(request):
    context = readiness_for_request(request)
    context["ready_count"] = sum(1 for step in context["workflow_steps"] if step["is_ready"])
    context["total_count"] = len(context["workflow_steps"])
    return render(request, "workflow/readiness.html", context)
