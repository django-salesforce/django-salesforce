"""
Common helpers for tests, like test decorators
"""
import uuid
try:
	from unittest import skip, skipUnless, expectedFailure
except ImportError:
	# old Python 2.6 (Django 1.4 - 1.6 simulated unittest2)
	from django.utils.unittest import skip, skipUnless, expectedFailure

# random string for tests that accidentally run concurrent
uid = '-' + str(uuid.uuid4())[:7]
