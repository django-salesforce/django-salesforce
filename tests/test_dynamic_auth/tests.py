from django.test import TestCase
from django.conf import settings
from django.db import connections
from salesforce.testrunner.example.models import User, Contact
from requests.exceptions import ConnectionError

class DynamicAuthTest(TestCase):
	def assertConnectionProblem(self, queryset):
		with self.assertRaises(Exception) as cm:
			len(queryset)
		exc = cm.exception
		self.assertTrue(isinstance(exc, (ConnectionError, LookupError, KeyError)))

	def test_dynamic_auth(self):
		"""
		Verify dynamic auth: Get access token from connection 'salesforce2'.
		The connection 'salesforce' is without credentials.
		Verify that exception is raised before dynamic_start or after dynamic_end.
		"""
		users = User.objects.all()[:2]
		# force connection to 'salesforce2' and get access_token from it.
		#_ = list(Contact.objects.all(using='salesforce2')[:1])
		with connections['salesforce2'].cursor() as cursor:
			access_token = cursor.oauth['access_token']
			instance_url = cursor.oauth['instance_url']
			#print(cursor.oauth)
		# verify fail
		self.assertConnectionProblem(users)
		# dynamic auth
		connections['salesforce'].sf_session.auth.dynamic_start(access_token, instance_url=instance_url)
		self.assertGreater(len(users), 0)
		connections['salesforce'].sf_session.auth.dynamic_end()
		# verify fail
		users = User.objects.all()[:2]
		self.assertConnectionProblem(users)
