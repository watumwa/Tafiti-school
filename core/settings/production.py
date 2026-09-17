import os
from .common import *
import pymysql
pymysql.install_as_MySQLdb()

DEBUG = False

SECRET_KEY = os.environ['SECRET_KEY']

# The parent login link is public-facing. In production it should remain
# available unless the school explicitly disables it in the environment.
PARENT_PORTAL_ENABLED = config_bool('PARENT_PORTAL_ENABLED', default=True)

ALLOWED_HOSTS = ["bayan-learningcenter.com", "www.bayan-learningcenter.com"]

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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'bayezieu_schooldb',
        'USER': 'bayezieu_bayan_user',
        'PASSWORD': '@bayan%dbuser',
        'HOST': '127.0.0.1',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
            'use_unicode': True,
            'init_command': "SET NAMES 'utf8mb4'"
        },
    }
}




# Email Configuration for SMTP (Using Gmail)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "bayern-learningcenter.com"
EMAIL_PORT = 465 
EMAIL_USE_SSL = True
EMAIL_HOST_USER = "bayan-learningcenter@bayern-learningcenter.com"
EMAIL_HOST_PASSWORD = "Mypp3[xD_Vdi" 
DEFAULT_FROM_EMAIL = "bayan-learningcenter@bayern-learningcenter.com"

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
