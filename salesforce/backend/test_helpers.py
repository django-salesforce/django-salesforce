"""
Common helpers for tests, like test decorators
"""
from unittest import skip, skipUnless, expectedFailure  # NOQA
import sys
import uuid

import django
from django.conf import settings
from salesforce import router

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
