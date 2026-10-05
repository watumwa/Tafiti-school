from .common import *

DEBUG = True

SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-development-only-change-me')



# Local development defaults to SQLite. Set DB_* environment variables in
# common.py if you explicitly need MySQL while developing.

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(BASE_DIR / 'db.sqlite3'),
    }
}
