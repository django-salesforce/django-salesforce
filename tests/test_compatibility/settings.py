from salesforce.testrunner.settings import *  # NOQA
from salesforce.testrunner.settings import INSTALLED_APPS

INSTALLED_APPS = tuple(x for x in INSTALLED_APPS if x != 'salesforce.testrunner.example')
INSTALLED_APPS += ('tests.test_compatibility',)
SF_PK = 'Id'
