from salesforce.testrunner.settings import *  # NOQA pylint: disable=unused-wildcard-import,wildcard-import
from salesforce.testrunner.settings import DATABASES, INSTALLED_APPS

SF_LAZY_CONNECT = True
# backup the static setting and set an empty dynamic setting
DATABASES = {
    'default': DATABASES['default'],

    'salesforce_copy': DATABASES['salesforce'],

    'salesforce': {
        'ENGINE': 'salesforce.backend',
        'AUTH': 'salesforce.auth.DynamicAuth',
    }
}
INSTALLED_APPS += ('tests.test_dynamic_auth',)
