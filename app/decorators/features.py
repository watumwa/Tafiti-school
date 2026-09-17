from functools import wraps

from django.conf import settings
from django.http import Http404


def feature_required(setting_name):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not getattr(settings, setting_name, False):
                raise Http404
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
