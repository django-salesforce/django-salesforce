# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

from django.test import TestCase
from django.conf import settings

from salesforce import auth
from salesforce.backend.test_helpers import default_is_sf, skipUnless, sf_alias


@skipUnless(default_is_sf, "Default database should be any Salesforce.")
class OAuthTest(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def validate_oauth(self, settings_dict):
        for key in ('access_token', 'id', 'instance_url', 'issued_at', 'signature'):
            if key not in settings_dict:
                self.fail("Missing %s key in returned oauth data." % key)
            elif not settings_dict[key]:
                self.fail("Empty value for %s key in returned oauth data." % key)

    def test_token_renewal(self):
        # import salesforce
        # _session=salesforce.backend.fake.base.FakeAuthSession()
        # _session.bind('default')
        import requests
        _session = requests.Session()

        auth_obj = auth.SalesforcePasswordAuth(sf_alias, settings_dict=settings.DATABASES[sf_alias],
                                               _session=_session)
        auth_obj.get_auth()
        self.validate_oauth(auth.oauth_data[sf_alias])
        old_data = auth.oauth_data

        self.assertIn(sf_alias, auth.oauth_data)
        auth_obj.del_token()
        self.assertNotIn(sf_alias, auth.oauth_data)

        auth_obj.get_auth()
        self.validate_oauth(auth.oauth_data[sf_alias])

        self.assertEqual(old_data[sf_alias]['access_token'], auth.oauth_data[sf_alias]['access_token'])
