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

# TODO more advanced methods with ouathlib can be implemented, but the simple doesn't require a spec package

log = logging.getLogger(__name__)

oauth_lock = threading.Lock()
oauth_data = None

def expire_token():
	global oauth_data
	with oauth_lock:
		oauth_data = None

def authenticate(settings_dict=dict()):
	"""
	Authenticate to the Salesforce API with the provided credentials.
	
	This function can be called multiple times, but will only make
	an external request once per the lifetime of the process. Subsequent
	calls to authenticate() will return the original oauth response.
	
	This function is thread-safe.
	"""
	global oauth_data
	# if another thread is in this method, wait for it to finish.
	# always release the lock no matter what happens in the block
	with oauth_lock:
		if(oauth_data):
			return oauth_data
		
		url = ''.join([settings_dict['HOST'], '/services/oauth2/token'])
		
		log.info("attempting authentication to %s" % url)
		response = requests.post(url, data=dict(
			grant_type		= 'password',
			client_id		= settings_dict['CONSUMER_KEY'],
			client_secret	= settings_dict['CONSUMER_SECRET'],
			username		= settings_dict['USER'],
			password		= settings_dict['PASSWORD'],
		))
		if(response.status_code == 200):
			log.info("successfully authenticated %s" % settings_dict['USER'])
			oauth_data = response.json()
		else:
			raise LookupError("oauth failed: %s: %s" % (settings_dict['USER'], response.text))
		
		return oauth_data
