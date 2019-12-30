from salesforce.testrunner.settings import *  # NOQA pylint: disable=unused-wildcard-import,wildcard-import
from salesforce.testrunner.settings import INSTALLED_APPS, MIDDLEWARE

INSTALLED_APPS += ('debug_toolbar', 'tests.t_debug_toolbar',)
MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
ROOT_URLCONF = 'tests.t_debug_toolbar.urls'
INTERNAL_IPS = ['127.0.0.1']
