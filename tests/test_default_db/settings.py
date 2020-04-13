from salesforce.testrunner.settings import *  # NOQA pylint: disable=unused-wildcard-import,wildcard-import
from salesforce.testrunner.settings import DATABASES

INSTALLED_APPS = ['tests.test_default_db']
DATABASES = {'default': DATABASES['default'], 'salesforce': DATABASES['salesforce']}
SALESFORCE_DB_ALIAS = 'default'
ROOT_URLCONF = None
# SF_LAZY_CONNECT = True
