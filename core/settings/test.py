"""Isolated settings for automated tests; never connects to production MySQL."""
from .common import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-only-not-for-production"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "school-tests"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
PARENT_PORTAL_ENABLED = True
ADMISSIONS_ENABLED = True
PUBLIC_ADMISSIONS_ENABLED = True
LIBRARY_ENABLED = True
