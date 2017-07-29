from salesforce.testrunner.settings import *  # NOQA
from salesforce.testrunner.settings import INSTALLED_APPS

INSTALLED_APPS = tuple(x for x in INSTALLED_APPS if x != 'salesforce.testrunner.example')
INSTALLED_APPS += ('tests.z_migrate_190',)
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
