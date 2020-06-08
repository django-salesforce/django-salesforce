from django.db import connections
from django.test import TestCase
import requests

from salesforce.backend.base import SalesforceError
from salesforce.testrunner.example.models import User


class DynamicAuthTest(TestCase):
    databases = '__all__'

    def assertConnectionProblem(self, queryset):
        with self.assertRaises(Exception) as cm:
            len(queryset)
        exc = cm.exception
        self.assertTrue(isinstance(exc, (requests.ConnectionError, SalesforceError)))

    def test_dynamic_auth(self):
        """
        Verify dynamic auth: Get access token from a backup 'salesforce_copy' of the normal connection.
        The dynamic connection 'salesforce' is without credentials.
        Verify that exception is raised before dynamic_start(...) or after dynamic_end().
        """
        users = User.objects.all()[:2]
        # get access_token from the 'salesforce_copy' connection.
        with connections['salesforce_copy'].cursor() as cursor:
            access_token = cursor.oauth['access_token']
            instance_url = cursor.oauth['instance_url']
        # verify that uncofigured dynamic-auth 'salesforce' fails initially
        self.assertConnectionProblem(users)
        # dynamic auth succeeds after getting the token
        connections['salesforce'].sf_session.auth.dynamic_start(access_token, instance_url=instance_url)
        self.assertGreater(len(users), 0)
        # verify that it fails again after 'dynamic_end()'
        connections['salesforce'].sf_session.auth.dynamic_end()
        users = User.objects.all()[:2]
        self.assertConnectionProblem(users)
