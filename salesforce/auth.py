# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
oauth login support for the Salesforce API
"""

import base64
import hashlib
import hmac
import logging
import requests
import threading
from django.db import connections
from salesforce.backend import MAX_RETRIES
from salesforce.backend.driver import DatabaseError
from salesforce.backend.adapter import SslHttpAdapter
from requests.auth import AuthBase

# TODO hy: more advanced methods with ouathlib can be implemented, but
#      the simple doesn't require a special package.

log = logging.getLogger(__name__)

oauth_lock = threading.Lock()
# The static "oauth_data" is useful for efficient static authentication with
# multithread server, whereas the thread local data in connection.sf_session.auth
# are necessary if dynamic auth is used.
oauth_data = {}


class SalesforceAuth(AuthBase):
	"""
	Attaches OAuth 2 Salesforce authentication to the Session
	or the given Request object.

	http://docs.python-requests.org/en/latest/user/advanced/#custom-authentication
	"""
	def __init__(self, db_alias, settings_dict=None, _session=None):
		self.db_alias = db_alias
		self.dynamic_token = None
		self._instance_url = None
		self.settings_dict = settings_dict or connections[db_alias].settings_dict
		self._session = _session or requests.Session()

	def __call__(self, r):
		"""standard auth hook on the "requests" request r"""
		if self.dynamic_token:
			access_token = self.dynamic_token
		else:
			access_token = str(self.authenticate()['access_token'])
		r.headers['Authorization'] = 'OAuth %s' % access_token
		return r

	def expire_token(self):
		with oauth_lock:
			del oauth_data[self.db_alias]

	def authenticate(self):
		"""
		Authenticate to the Salesforce API with the provided credentials.
		
			Params:
				db_alias:  The database alias e.g. the default SF alias 'salesforce'.
				settings_dict: It is only important for the first connection.
						Should be taken from django.conf.DATABASES['salesforce'],
						because it is not known in connection.settings_dict initially.
				_session: only for tests

		This function can be called multiple times, but will only make
		an external request once per the lifetime of the auth token. Subsequent
		calls to authenticate() will return the original oauth response.
		
		This function is thread-safe.
		"""
		# if another thread is in this method, wait for it to finish.
		# always release the lock no matter what happens in the block
		db_alias = self.db_alias
		if not db_alias in connections:
			raise KeyError("authenticate function signature has been changed. "
					"The db_alias parameter more important than settings_dict")
		with oauth_lock:
			if not db_alias in oauth_data:
				settings_dict = self.settings_dict
				if settings_dict['USER'] == 'dynamic auth':
					oauth_data[db_alias] = {'instance_url': settings_dict['HOST']}
				else:
					url = ''.join([settings_dict['HOST'], '/services/oauth2/token'])
					
					log.info("attempting authentication to %s" % settings_dict['HOST'])
					self._session.mount(settings_dict['HOST'], SslHttpAdapter(max_retries=MAX_RETRIES))
					response = self._session.post(url, data=dict(
						grant_type		= 'password',
						client_id		= settings_dict['CONSUMER_KEY'],
						client_secret	= settings_dict['CONSUMER_SECRET'],
						username		= settings_dict['USER'],
						password		= settings_dict['PASSWORD'],
					))
					if response.status_code == 200:
						response_data = response.json()
						calc_signature = (base64.b64encode(hmac.new(
								key=settings_dict['CONSUMER_SECRET'].encode('ascii'),
								msg=(response_data['id'] + response_data['issued_at']).encode('ascii'),
								digestmod=hashlib.sha256).digest())).decode('ascii')
						if calc_signature == response_data['signature']:
							log.info("successfully authenticated %s" % settings_dict['USER'])
							oauth_data[db_alias] = response_data
						else:
							raise RuntimeError('Invalid auth signature received')
					else:
						raise LookupError("oauth failed: %s: %s" % (settings_dict['USER'], response.text))
			
			return oauth_data[db_alias]

	def reauthenticate(self):
		if connections['salesforce'].sf_session.auth.dynamic_token is None:
			self.expire_token()
			return str(self.authenticate()['access_token'])
		else:
			# It is expected that with dynamic authentication we get a token that
			# is valid at least for a few future seconds, because we don't get
			# any password or permanent permission for it from the user.
			raise DatabaseError("Dynamically authenticated connection can never reauthenticate.")

	@property
	def instance_url(self):
		if self._instance_url:
			return self._instance_url
		else:
			# TODO self._session
			return self.authenticate()['instance_url']

	def dynamic_start(self, access_token, instance_url=None):
		"""
		Set the access token dynamically according to the current user.

		Use it typically at the beginning of Django request in your middleware by:
			connections['salesforce'].sf_session.auth.dynamic_start(access_token)
		"""
		self.dynamic_token = access_token
		self._instance_url = instance_url

	def dynamic_end(self):
		"""
		Clear the dynamic access token.
		"""
		self.dynamic_token = None
		self._instance_url = None
