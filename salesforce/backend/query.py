import copy, urllib

from django.core import serializers
from django.conf import settings
from django.db.models import query as django_query
from django.utils.encoding import force_unicode
from django.db.backends.signals import connection_created
 
import restkit

from django_roa.db import query, exceptions

from salesforce import sfauth
from salesforce.backend import compiler

try:
	import json
except ImportError, e:
	import simplejson as json

class SalesforceQuerySet(django_query.QuerySet):
	def iterator(self):
		"""
		An iterator over the results from applying this QuerySet to the
		remote web service.
		"""
		from django.db import connections
		sql, params = compiler.SQLCompiler(self.query, connections[self.db], None).as_sql()
		cursor = CursorWrapper(connections[self.db])
		cursor.execute(rendered_query, params)
		return cursor.fetchmany()

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
		
		ROA_FORMAT = getattr(settings, "ROA_FORMAT", 'salesforce')
		
		def _iterate(d):
			d = json.loads(d)
			for record in d['records']:
				attribs = record.pop('attributes')
				yield record.values()
	
		# self.results = serializers.deserialize(ROA_FORMAT, response)
		self.results = _iterate(response)
	
	def fetchone(self):
		res = self.results.next()
		return res
	
	def fetchmany(self, size):
		result = []
		for index in range(size):
			try:
				if(index == size-1):
					return result
				result.append(self.fetchone())
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
