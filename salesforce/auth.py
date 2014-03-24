# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
oauth login support for the Salesforce API
"""

import logging
import requests
import threading
from django.db import connections
from salesforce.backend import sf_alias, MAX_RETRIES
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase

# TODO more advanced methods with ouathlib can be implemented, but the simple doesn't require a spec package

log = logging.getLogger(__name__)

oauth_lock = threading.Lock()
oauth_data = {}

def expire_token(db_alias=None):
	with oauth_lock:
		del oauth_data[db_alias or sf_alias]

def authenticate(settings_dict=None, db_alias=None):
	"""
	Authenticate to the Salesforce API with the provided credentials.
	
        Params:
			settings_dict: Should be obtained from django.conf.DATABASES['salesforce'].
			db_alias:  The database alias e.g. the default alias 'salesforce'.

	This function can be called multiple times, but will only make
	an external request once per the lifetime of the process. Subsequent
	calls to authenticate() will return the original oauth response.
	
	This function is thread-safe.
	"""
	# if another thread is in this method, wait for it to finish.
	# always release the lock no matter what happens in the block
	db_alias = db_alias or sf_alias
	with oauth_lock:
		if db_alias in oauth_data:
			return oauth_data[db_alias]
		
		settings_dict = settings_dict or connections[db_alias].settings_dict
		url = ''.join([settings_dict['HOST'], '/services/oauth2/token'])
		
		log.info("attempting authentication to %s" % url)
		session = requests.Session()
		session.mount(settings_dict['HOST'], HTTPAdapter(max_retries=MAX_RETRIES))
		response = session.post(url, data=dict(
			grant_type		= 'password',
			client_id		= settings_dict['CONSUMER_KEY'],
			client_secret	= settings_dict['CONSUMER_SECRET'],
			username		= settings_dict['USER'],
			password		= settings_dict['PASSWORD'],
		))
		if response.status_code == 200:
			log.info("successfully authenticated %s" % settings_dict['USER'])
			oauth_data[db_alias] = response.json()
		else:
			raise LookupError("oauth failed: %s: %s" % (settings_dict['USER'], response.text))
		
		return oauth_data[db_alias]

class SalesforceAuth(AuthBase):
	"""
	Attaches OAuth 2 Salesforce authentication to the Session
	or the given Request object.
	"""
	def __init__(self, db_alias):
		self.db_alias = db_alias

	def __call__(self, r):
		r.headers['Authorization'] = 'OAuth %s' % authenticate(db_alias=self.db_alias)['access_token']
		return r
