import os
from urllib.parse import unquote, urlparse
from .common import *
from django.core.exceptions import ImproperlyConfigured
import pymysql
pymysql.install_as_MySQLdb()

DEBUG = False

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'vercel-cache',
    }
}
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler'
        }
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO')
        }
    }
}

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY') or os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be configured in production.')

# The parent login link is public-facing. In production it should remain
# available unless the school explicitly disables it in the environment.
PARENT_PORTAL_ENABLED = config_bool('PARENT_PORTAL_ENABLED', default=True)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        'ALLOWED_HOSTS',
        'bayan-learningcenter.com,www.bayan-learningcenter.com,.vercel.app',
    ).split(',')
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        'CSRF_TRUSTED_ORIGINS',
        'https://*.vercel.app,https://bayan-learningcenter.com,https://www.bayan-learningcenter.com',
    ).split(',')
    if origin.strip()
]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'schooldb',
#         'USER': 'schooluser',
#         'PASSWORD': 'root@admin',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }

# ``DATABASE_URL`` is the explicit application setting.  When the database is
# attached through Vercel's Neon integration, Vercel instead provides one of
# the managed Postgres URLs below.  Prefer a direct/non-pooling URL for Django
# migrations and fall back to the pooled URL for normal requests.
database_url = (
    os.environ.get('DATABASE_URL')
    or os.environ.get('POSTGRES_URL_NON_POOLING')
    or os.environ.get('DATABASE_URL_UNPOOLED')
    or os.environ.get('POSTGRES_URL')
)
if database_url:
    parsed_database_url = urlparse(database_url)
    database_engine = {
        'mysql': 'django.db.backends.mysql',
        'mysql2': 'django.db.backends.mysql',
        'sqlite': 'django.db.backends.sqlite3',
        'postgres': 'django.db.backends.postgresql',
        'postgresql': 'django.db.backends.postgresql',
    }.get(parsed_database_url.scheme)
    if not database_engine:
        raise ValueError('DATABASE_URL must use mysql, postgres, or sqlite')

    if database_engine == 'django.db.backends.sqlite3':
        DATABASES = {'default': {'ENGINE': database_engine, 'NAME': parsed_database_url.path}}
    else:
        DATABASES = {
            'default': {
                'ENGINE': database_engine,
                'NAME': parsed_database_url.path.lstrip('/'),
                'USER': unquote(parsed_database_url.username or ''),
                'PASSWORD': unquote(parsed_database_url.password or ''),
                'HOST': parsed_database_url.hostname or '',
                'PORT': str(parsed_database_url.port or ''),
                'OPTIONS': {'charset': 'utf8mb4'} if database_engine.endswith('mysql') else {},
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('MYSQL_DATABASE', 'bayezieu_schooldb'),
            'USER': os.environ.get('MYSQL_USER', 'bayezieu_bayan_user'),
            'PASSWORD': os.environ.get('MYSQL_PASSWORD', ''),
            'HOST': os.environ.get('MYSQL_HOST', '127.0.0.1'),
            'PORT': os.environ.get('MYSQL_PORT', '3306'),
            'OPTIONS': {'charset': 'utf8mb4', 'use_unicode': True},
        }
    }




# SMTP credentials are configured through environment variables in common.py.
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', EMAIL_BACKEND)
EMAIL_HOST = os.environ.get('EMAIL_HOST', EMAIL_HOST)
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', EMAIL_PORT))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', EMAIL_HOST_USER)
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', EMAIL_HOST_PASSWORD)
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', DEFAULT_FROM_EMAIL)

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'public', 'static')

MEDIA_URL = '/media/'
MEDIA_ROOT = '/tmp/tafiti-media'
VERCEL_BLOB_READ_WRITE_TOKEN = os.environ.get('BLOB_READ_WRITE_TOKEN', '')
STORAGES = {
    'default': {
        'BACKEND': 'app.storage.VercelBlobStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}
