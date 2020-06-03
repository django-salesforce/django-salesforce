from salesforce.testrunner.settings import *  # NOQA pylint: disable=unused-wildcard-import,wildcard-import
from salesforce.testrunner.settings import INSTALLED_APPS

# replace the test app
INSTALLED_APPS = [x for x in INSTALLED_APPS if not x.startswith('salesforce.testrunner.')]
INSTALLED_APPS += ['tests.tooling']
ROOT_URLCONF = 'tests.tooling.urls'
PK_ID = 'id'
