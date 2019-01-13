"""
Common helpers for tests, like test decorators
"""
from unittest import skip, skipUnless, expectedFailure  # NOQA
import sys
import uuid

import django
from django.conf import settings

from salesforce import router
from salesforce.dbapi.test_helpers import LazyTestMixin  # NOQA

# uid strings for tests that accidentally run concurrent
uid_random = '-' + str(uuid.uuid4())[:7]
# this is the same as the name of tox test environment, e.g. 'py35-dj110'
uid_version = 'py{0}{1}-dj{2}{3}'.format(*(sys.version_info[:2] + django.VERSION[:2]))

sf_alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
default_is_sf = router.is_sf_database(sf_alias)
current_user = settings.DATABASES[sf_alias]['USER']

def expectedFailureIf(condition):
    """Conditional 'expectedFailure' decorator for TestCase"""
    if condition:
        return expectedFailure
    else:
        return lambda func: func


class QuietSalesforceErrors(object):
    """Context manager that helps expected SalesforceErrors to be quiet"""
    def __init__(self, alias):
        from django.db import connections
        self.connection = connections[alias]

    def __enter__(self):
        if hasattr(self.connection, 'debug_silent'):
            self.save_debug_silent = self.connection.debug_silent
            self.connection.debug_silent = True
        return self

    def __exit__(self, type, value, traceback):
        try:
            self.connection.debug_silent = self.save_debug_silent
        except AttributeError:
            pass


def no_soap_decorator(f):
    """Decorator to not temporarily use SOAP API (Beatbox)"""
    from functools import wraps
    import salesforce.backend.driver
    @wraps(f)
    def wrapper(*args, **kwds):
        beatbox_orig = salesforce.backend.driver.beatbox
        setattr(salesforce.backend.driver, 'beatbox', None)
        try:
            return f(*args, **kwds)
        finally:
            setattr(salesforce.backend.driver, 'beatbox', beatbox_orig)
    return wrapper
