from salesforce.testrunner.settings import *

# replace the test app
INSTALLED_APPS = tuple(x for x in INSTALLED_APPS if x != 'salesforce.testrunner.example')
INSTALLED_APPS += ('tests.inspectdb',)
