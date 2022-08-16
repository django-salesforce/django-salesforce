import unittest
import requests
from salesforce import auth
from salesforce.dbapi import driver
import salesforce.testrunner.settings

sf_alias = 'salesforce'
settings_dict = salesforce.testrunner.settings.DATABASES[sf_alias]


class Test(unittest.TestCase):

    def test_no_django(self):
        self.assertRaises(ImportError, __import__, 'django.core')

    def test_auth_standard(self):
        auth.SalesforcePasswordAuth(sf_alias, settings_dict=settings_dict)


class OAuthTest(unittest.TestCase):

    def validate_oauth(self, settings_dict):
        for key in ('access_token', 'id', 'instance_url', 'issued_at', 'signature'):
            if key not in settings_dict:
                self.fail("Missing %s key in returned oauth data." % key)
            elif not settings_dict[key]:
                self.fail("Empty value for %s key in returned oauth data." % key)

    def test_token_renewal(self):
        # _session=salesforce.backend.fake.base.FakeAuthSession()
        # _session.bind('default')
        _session = requests.Session()

        auth_obj = auth.SalesforcePasswordAuth(sf_alias, settings_dict=settings_dict,
                                               _session=_session)
        auth_obj.get_auth()
        self.validate_oauth(auth.oauth_data[sf_alias])
        old_data = auth.oauth_data

        self.assertIn(sf_alias, auth.oauth_data)
        auth_obj.del_token()
        self.assertNotIn(sf_alias, auth.oauth_data)

        _session.close()  # close to prevent ResourceWarning: unclosed <ssl.SSLSocket...>
        auth_obj.get_auth()
        self.validate_oauth(auth.oauth_data[sf_alias])

        self.assertEqual(old_data[sf_alias]['access_token'], auth.oauth_data[sf_alias]['access_token'])
        _session.close()


class CursorTest(unittest.TestCase):
    """Currently tested only methods not covered by Django test"""

    def test_scroll(self):
        with driver.get_connection('salesforce', settings_dict=settings_dict) as connection:
            # the context manager for cursor is not important
            with connection.cursor() as cursor:
                cursor.execute("select Name from Contact limit 5")
                result = cursor.fetchall()
                # no more data
                self.assertEqual(cursor.fetchone(), None)
                self.assertEqual(cursor.fetchall(), [])
                self.assertEqual(cursor.fetchmany(), [])
                self.assertEqual(cursor.fetchmany(size=10), [])
                # scroll to replay the data
                cursor.scroll(0, 'absolute')
                result2 = cursor.fetchall()
                self.assertEqual(result2, result)

    def test_explain(self) -> None:
        connection = driver.get_connection('salesforce', settings_dict=settings_dict)
        cursor = connection.cursor()

        cursor.execute("EXPLAIN SELECT Name FROM Contact")
        self.assertRegex(cursor.fetchone()[0], r"^{'plans': \[{")  # type: ignore[index]
        last_detail = list(cursor.fetchall())[-1][0]
        self.assertEqual(last_detail, " 'sourceQuery': 'SELECT Name FROM Contact'}")

        connection.close()
