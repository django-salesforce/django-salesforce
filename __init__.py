import logging, threading, urllib, traceback

from django.conf import settings

import oauth2

log = logging.getLogger(__name__)
lock = threading.Lock()
oauth_data = None

def authenticate():
	global oauth_data
	if(oauth_data):
		return oauth_data
	
	lock.acquire()
	try:
		consumer = oauth2.Consumer(key=settings.SF_CONSUMER_KEY, secret=settings.SF_CONSUMER_SECRET)
		client = oauth2.Client(consumer)
		url = ''.join([settings.SF_SERVER, '/services/oauth2/token'])
		response, content = client.request(url, 'POST', body=urllib.urlencode(dict(
			grant_type      = 'password',
			client_id       = settings.SF_CONSUMER_KEY,
			client_secret   = settings.SF_CONSUMER_SECRET,
			username        = settings.SF_USERNAME,
			password        = settings.SF_PASSWORD,
		)))
		if(response['status'] == '200'):
			oauth_data = content
		else:
			log.error("HTTP Error in authenticate(): %s" % oauth_data)
	except Exception, e:
		log.error("Exception in authenticate(): %s" % traceback.format_exc())
		lock.release()
	
	return oauth_data
