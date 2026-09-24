from django.conf import settings


class UpdateUnfoldMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from app.models.school_settings import SchoolSetting

        try:
            school_name = SchoolSetting.objects.values_list("school_name", flat=True).first()
        except Exception:
            school_name = None

        school_name = (school_name or "School").strip()
        settings.UNFOLD.update({
            "SITE_TITLE": f"{school_name} Admin",
            "SITE_HEADER": school_name,
        })
        return self.get_response(request)