"""
Common helpers for tests, like test decorators
"""
from django.conf import settings
from salesforce import router
import uuid
try:
	from unittest import skip, skipUnless, expectedFailure
except ImportError:
	# old Python 2.6 (Django 1.4 - 1.6 simulated unittest2)
	from django.utils.unittest import skip, skipUnless, expectedFailure

# random string for tests that accidentally run concurrent
uid = '-' + str(uuid.uuid4())[:7]

sf_alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
default_is_sf = router.is_sf_database(sf_alias)
current_user = settings.DATABASES[sf_alias]['USER']

def expectedFailureIf(condition):
	"""Conditional 'expectedFailure' decorator for TestCase"""
	if condition:
		return expectedFailure
	else:
		return lambda func: func
