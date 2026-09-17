from .common import *
import pymysql
pymysql.install_as_MySQLdb()


DEBUG = True

SECRET_KEY = 'django-insecure-gqgpv+7+nke4*fefzsr63+a=r0!!t@bgn!_1a*5(_^ow@^3t)('



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
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(BASE_DIR / 'db.sqlite3'),
    }
}
