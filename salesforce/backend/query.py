import copy, urllib, logging

from django.core import serializers
from django.conf import settings
from django.db.models import query as django_query
from django.utils.encoding import force_unicode
from django.db.backends.signals import connection_created
from django.core.serializers import python

import restkit

from django_roa.db import query, exceptions

from salesforce import sfauth
from salesforce.backend import compiler

try:
	import json
except ImportError, e:
	import simplejson as json

log = logging.getLogger(__name__)

class SalesforceQuerySet(django_query.QuerySet):
	def iterator(self):
		"""
		An iterator over the results from applying this QuerySet to the
		remote web service.
		"""
		from django.db import connections
		sql, params = compiler.SQLCompiler(self.query, connections[self.db], None).as_sql()
		log.debug(sql % params)
		cursor = CursorWrapper(connections[self.db])
		cursor.execute(sql, params)

		def _mkmodels(data):
			for record in data:
				attribs = record.pop('attributes')
				yield dict(
					model	= 'salesforce.%s' % attribs['type'],
					pk		= record.pop('Id'),
					fields  = record,
				)
		
		ROA_FORMAT = getattr(settings, "ROA_FORMAT", 'salesforce')
		response = cursor.fetchmany()
		for res in python.Deserializer(_mkmodels(response)):
			yield res.object

class CursorWrapper(object):
	def __init__(self, conn):
		connection_created.send(sender=self.__class__, connection=self)
		self.oauth = sfauth.authenticate(conn.settings_dict)
	
	def execute(self, q, args=None):
		headers = copy.copy(query.ROA_HEADERS)
		headers['Authorization'] = 'OAuth %s' % self.oauth['access_token']
		
		url = u'%s%s?%s' % (self.oauth['instance_url'], '/services/data/v23.0/query', urllib.urlencode(dict(
			q	= q % args,
		)))
		
		resource = restkit.Resource(url)
		
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
		
		def _iterate(d):
			d = json.loads(d)
			for record in d['records']:
				yield record
	
		self.results = _iterate(response)
	
	def fetchone(self):
		try:
			res = self.results.next()
			return res
		except StopIteration:
			return None
	
	def fetchmany(self, size=0):
		result = []
		counter = 0
		while(True):
			try:
				if(counter == size-1):
					return result
				if(size != 0):
					counter += 1
				row = self.fetchone()
				if not(row):
					return result
				result.append(row)
			except StopIteration:
				pass
		return result

	def fetchall(self):
		result = []
		for index in range(size):
			try:
				result.append(self.fetchone())
			except StopIteration:
				pass
		return result

serializers.register_serializer('salesforce', 'salesforce.rest')
