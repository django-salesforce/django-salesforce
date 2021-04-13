"""
Generated by 'django-admin startproject' using Django 3.0.5.
"""

import os
from typing import List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = ')k(*qyju@bs21xtn%$2n*fimhmcq^o&cyl2kgk#zmm8ld*nxtx'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []  # type: List[str]

INSTALLED_APPS = [
    'tests.no_salesforce'
]

ROOT_URLCONF = None

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}


TIME_ZONE = 'UTC'
USE_TZ = True
STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
