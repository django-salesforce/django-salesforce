# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

import copy, logging, threading, urllib

try:
	import json
except ImportError:
	import simplejson as json

import oauth2

log = logging.getLogger(__name__)

oauth_lock = threading.Lock()
oauth_data = None

def authenticate(settings_dict=dict()):
	oauth_lock.acquire()
	try:
		global oauth_data
		if(oauth_data):
			return oauth_data
		
		consumer = oauth2.Consumer(key=settings_dict['CONSUMER_KEY'], secret=settings_dict['CONSUMER_SECRET'])
		client = oauth2.Client(consumer)
		url = ''.join([settings_dict['HOST'], '/services/oauth2/token'])
		
		log.debug("Attempting authentication to %s" % url)
		response, content = client.request(url, 'POST', body=urllib.urlencode(dict(
			grant_type		= 'password',
			client_id		= settings_dict['CONSUMER_KEY'],
			client_secret	= settings_dict['CONSUMER_SECRET'],
			username		= settings_dict['USER'],
			password		= settings_dict['PASSWORD'],
		)))
		log.debug("successfully authenticated %s" % settings_dict['USER'])
		if(response['status'] == '200'):
			oauth_data = json.loads(content)
		else:
			log.error("HTTP Error in authenticate(): %s" % oauth_data)
		
		return oauth_data
	finally:
		oauth_lock.release()

