from django.shortcuts import render


def csrf_failure(request, reason=""):
    """Replace Django's technical CSRF screen with a safe recovery path."""
    if request.path.startswith("/parent/"):
        return render(
            request,
            "parent_portal/csrf_failure.html",
            {"portal_guest": True},
            status=403,
        )
    return render(request, "errors/csrf_failure.html", status=403)
