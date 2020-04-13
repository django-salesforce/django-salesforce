from salesforce.testrunner.settings import *  # NOQA pylint: disable=unused-wildcard-import,wildcard-import
from salesforce.testrunner.settings import INSTALLED_APPS

INSTALLED_APPS = [x for x in INSTALLED_APPS if x != 'salesforce.testrunner.example']
INSTALLED_APPS += ['tests.test_migrate']
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'db_tmp_default',
    },
    'salesforce': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'db_tmp_salesforce',
    },
}
ROOT_URLCONF = None
