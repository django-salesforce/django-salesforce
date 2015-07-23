# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

from django.test import TestCase
from django.conf import settings

from salesforce import auth
from salesforce.backend import sf_alias
from salesforce.testrunner.example import models
from salesforce.tests.test_integration import default_is_sf
try:
	from unittest import skip, skipUnless
except ImportError:
	# old Python 2.6 (Django 1.4 - 1.6 simulated unittest2)
	from django.utils.unittest import skip, skipUnless

import logging
log = logging.getLogger(__name__)

@skipUnless(default_is_sf, "Default database should be any Salesforce.")
class OAuthTest(TestCase):
	def setUp(self):
		pass
	
	def tearDown(self):
		pass
	
	def validate_oauth(self, d):
		for key in ('access_token', 'id', 'instance_url', 'issued_at', 'signature'):
			if(key not in d):
				self.fail("Missing %s key in returned oauth data." % key)
			elif(not d[key]):
				self.fail("Empty value for %s key in returned oauth data." % key)
	
	def test_token_renewal(self):
		auth.authenticate(sf_alias, settings_dict=settings.DATABASES[sf_alias])
		self.validate_oauth(auth.oauth_data[sf_alias])
		old_data = auth.oauth_data
		
		self.assertIn(sf_alias, auth.oauth_data)
		auth.expire_token()
		self.assertNotIn(sf_alias, auth.oauth_data)
		
		auth.authenticate(sf_alias, settings_dict=settings.DATABASES[sf_alias])
		self.validate_oauth(auth.oauth_data[sf_alias])
		
		self.assertEqual(old_data[sf_alias]['access_token'], auth.oauth_data[sf_alias]['access_token'])
