# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

from django.test import TestCase
from django.conf import settings

from salesforce import auth
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
		auth.authenticate(settings.DATABASES[settings.SALESFORCE_DB_ALIAS])
		self.validate_oauth(auth.oauth_data)
		old_data = auth.oauth_data
		
		auth.expire_token()
		self.assertEqual(auth.oauth_data, None)
		
		auth.authenticate(settings.DATABASES[settings.SALESFORCE_DB_ALIAS])
		self.validate_oauth(auth.oauth_data)
		
		self.assertEqual(old_data['access_token'], auth.oauth_data['access_token'])
