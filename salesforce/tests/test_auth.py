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

import logging
log = logging.getLogger(__name__)

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
		auth.authenticate(settings.DATABASES[sf_alias])
		self.validate_oauth(auth.oauth_data[sf_alias])
		old_data = auth.oauth_data
		
		auth.expire_token()
		self.assertEqual(auth.oauth_data, {})
		
		auth.authenticate(settings.DATABASES[sf_alias])
		self.validate_oauth(auth.oauth_data[sf_alias])
		
		self.assertEqual(old_data[sf_alias]['access_token'], auth.oauth_data[sf_alias]['access_token'])
