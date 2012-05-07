# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

import copy, logging, threading, urllib

from django.core.serializers.python import Serializer as PythonSerializer
from django.core.serializers.python import Deserializer as PythonDeserializer

try:
	from cStringIO import StringIO
except ImportError:
	from StringIO import StringIO

try:
	import json
except ImportError:
	import simplejson as json

import oauth2

log = logging.getLogger(__name__)

oauth_lock = threading.Lock()
oauth_data = None

class Serializer(PythonSerializer):
	"""
	Convert a queryset to JSON.
	"""
	internal_use_only = False

	def end_serialization(self):
		json.dump(self.objects, self.stream, **self.options)

	def getvalue(self):
		if callable(getattr(self.stream, 'getvalue', None)):
			return self.stream.getvalue()

def Deserializer(stream_or_string, **options):
	"""
	Deserialize a stream or string of JSON data.
	"""
	if isinstance(stream_or_string, basestring):
		stream = StringIO(stream_or_string)
	else:
		stream = stream_or_string
	
	def _mkrecords(data):
		for record in data['records']:
			attribs = record.pop('attributes')
			yield dict(
				model	= 'salesforce.%s' % attribs['type'],
				pk		= record.pop('Id'),
				fields  = record,
			)
	
	data = json.load(stream)
	for obj in PythonDeserializer(_mkrecords(data), **options):
		yield obj

def authenticate(settings_dict=dict()):
	oauth_lock.acquire()
	try:
		global oauth_data
		if(oauth_data):
			return oauth_data
		
		if(django_roa.Manager != SalesforceManager):
			django_roa.Manager = SalesforceManager
		
		consumer = oauth2.Consumer(key=settings_dict['CONSUMER_KEY'], secret=settings_dict['CONSUMER_SECRET'])
		client = oauth2.Client(consumer)
		url = ''.join([settings_dict['HOST'], '/services/oauth2/token'])
		response, content = client.request(url, 'POST', body=urllib.urlencode(dict(
			grant_type		= 'password',
			client_id		= settings_dict['CONSUMER_KEY'],
			client_secret	= settings_dict['CONSUMER_SECRET'],
			username		= settings_dict['USER'],
			password		= settings_dict['PASSWORD'],
		)))
		if(response['status'] == '200'):
			oauth_data = json.loads(content)
		else:
			log.error("HTTP Error in authenticate(): %s" % oauth_data)
		
		return oauth_data
	finally:
		oauth_lock.release()

