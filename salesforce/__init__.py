import logging, threading, urllib, traceback, copy

from django.conf import settings
from django.core import serializers
from django.utils.encoding import force_unicode
from django.db.models import query as django_query

import django_roa
from django_roa.db import query, managers, exceptions

import restkit

import oauth2

try:
	import json
except ImportError:
	import simplejson as json

log = logging.getLogger(__name__)
lock = threading.Lock()
oauth_data = None

def configure_roa():
	django_roa.Manager = SalesforceManager
	serializers.register_serializer('salesforce', 'fu_web.salesforce.sfjson')

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
			grant_type		= 'password',
			client_id		= settings.SF_CONSUMER_KEY,
			client_secret	= settings.SF_CONSUMER_SECRET,
			username		= settings.SF_USERNAME,
			password		= settings.SF_PASSWORD,
		)))
		if(response['status'] == '200'):
			oauth_data = json.loads(content)
		else:
			log.error("HTTP Error in authenticate(): %s" % oauth_data)
	except Exception, e:
		log.error("Exception in authenticate(): %s" % traceback.format_exc())
		lock.release()
	
	return oauth_data

class SalesforceManager(managers.ROAManager):
	def get_query_set(self):
		"""
		Returns a QuerySet which access remote resources.
		"""
		return SalesforceQuerySet(self.model)

class SalesforceQuerySet(django_query.QuerySet):
	def iterator(self):
		"""
		An iterator over the results from applying this QuerySet to the
		remote web service.
		"""
		headers = copy.copy(query.ROA_HEADERS)
		oauth = authenticate()
		headers['Authorization'] = 'OAuth %s' % oauth['access_token']
		resource = restkit.Resource(self.model.get_resource_url_list(self, server=oauth['instance_url']))
		
		try:
			response = resource.get(headers=headers)
		except restkit.ResourceNotFound:
			return
		except Exception, e:
			raise exceptions.ROAException(e)
		
		body = response.body_string()
		response = force_unicode(body).encode(settings.DEFAULT_CHARSET)
		for local_name, remote_name in query.ROA_MODEL_NAME_MAPPING:
			response = response.replace(remote_name, local_name)
		
		ROA_FORMAT = getattr(settings, "ROA_FORMAT", 'json')
		for res in serializers.deserialize(ROA_FORMAT, response):
			obj = res.object
			yield obj

configure_roa()
