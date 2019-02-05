from salesforce.testrunner.settings import *  # NOQA pylint: disable=unused-wildcard-import,wildcard-import
from salesforce.testrunner.settings import INSTALLED_APPS

INSTALLED_APPS = tuple(x for x in INSTALLED_APPS if x != 'salesforce.testrunner.example')
INSTALLED_APPS += ('tests.test_compatibility',)
SF_PK = 'Id'
ROOT_URLCONF = None
