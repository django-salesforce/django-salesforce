from django.test import TestCase
from django.conf import settings
from django.db import connections
from salesforce.testrunner.example.models import User
from requests.exceptions import ConnectionError


class LazyTest(TestCase):
    databases = '__all__'

    def test_lazy_connection(self):
        """
        Verify that the plain access to SF connection object does not raise
        exceptions with SF_LAZY_CONNECT if SF is not accessible.
        """
        # verify that access to a broken connection does not raise exception
        sf_conn = connections['salesforce']
        # try to authenticate on a temporary broken host
        users = User.objects.all()
        with self.assertRaises(Exception) as cm:
            len(users[:5])
        exc = cm.exception
        self.assertTrue(isinstance(exc, (ConnectionError, LookupError)))
        # fix the host name and verify that the connection works now
        sf_conn.connection.settings_dict.update(settings.ORIG_SALESFORCE_DB)
        self.assertGreater(len(users[:5]), 0)
