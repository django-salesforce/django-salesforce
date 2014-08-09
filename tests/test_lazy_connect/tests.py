from django.test import TestCase
from django.db import connections

class LazyTest(TestCase):
	def test_lazy_connection(self):
		"""
		Verify that the plain access to SF connection object does not raises
		exceptions vith SF_LAZY_CONNECT if SF is not accessible.
		"""
		_ = connections['salesforce']
