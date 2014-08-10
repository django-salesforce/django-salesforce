from django.test import TestCase
from django.conf import settings
from django.db import connections
from salesforce.testrunner.example.models import User

class LazyTest(TestCase):
	def test_lazy_connection(self):
		"""
		Verify that the plain access to SF connection object does not raises
		exceptions vith SF_LAZY_CONNECT if SF is not accessible.
		"""
		# verify that access to a broken connection does not raise exception
		sf_conn = connections['salesforce']
		# fix the host name and verify that the connection works
		sf_conn.settings_dict['HOST']= settings.ORIG_SALESFORCE_HOST
		users = User.objects.all()
		self.assertGreater(len(users[:5]), 0)
