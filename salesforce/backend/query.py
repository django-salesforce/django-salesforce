import copy, urllib, logging, types, datetime, decimal

from django.core import serializers, exceptions
from django.conf import settings
from django.db.models import query
from django.db.models.sql import Query
from django.db.models.sql.constants import GET_ITERATOR_CHUNK_SIZE
from django.utils.encoding import force_unicode
from django.db.backends.signals import connection_created
from django.core.serializers import python

import restkit

from salesforce import sfauth
from salesforce.backend import compiler

try:
	import json
except ImportError, e:
	import simplejson as json

log = logging.getLogger(__name__)

def quoted_string_literal(s, d):
	# okay, so, according to the SQL standard, this should be all you need to do to escape
	# any kind of string.
	try:
		return "'%s'" % (s.replace("'", "''"),)
	except TypeError, e:
		raise NotImplementedError("Cannot quote %r objects: %r" % (type(s), s))

class SalesforceQuerySet(query.QuerySet):
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
					fields	= record,
				)
		
		response = cursor.fetchmany(GET_ITERATOR_CHUNK_SIZE)
		for res in python.Deserializer(_mkmodels(response)):
			yield res.object

class SalesforceQuery(Query):
	from salesforce.backend import aggregates
	aggregates_module = aggregates

class CursorWrapper(object):
	def __init__(self, conn):
		connection_created.send(sender=self.__class__, connection=self)
		self.oauth = sfauth.authenticate(conn.settings_dict)
		self.results = iter([])
	
	def process_args(self, args):
		def _escape(item, conv):
			return conv.get(type(item), conv[str])(item, conv)
		return [_escape(x, conversions) for x in args]
	
	def execute(self, q, args=None):
		headers = dict()
		headers['Authorization'] = 'OAuth %s' % self.oauth['access_token']
		
		processed_args = self.process_args(args)
		url = u'%s%s?%s' % (self.oauth['instance_url'], '/services/data/v23.0/query', urllib.urlencode(dict(
			q	= q % tuple(processed_args),
		)))
		
		resource = restkit.Resource(url)
		
		try:
			response = resource.get(headers=headers)
		except restkit.ResourceNotFound, e:
			log.error("Couldn't connect to Salesforce API (404): %s" % e)
			return
		except restkit.ResourceGone, e:
			log.error("Couldn't connect to Salesforce API (410): %s" % e)
			return
		except restkit.Unauthorized, e:
			raise exceptions.PermissionDenied(str(e))
		except restkit.RequestFailed, e:
			data = json.loads(str(e))[0]
			if(data['errorCode'] == 'INVALID_FIELD'):
				raise exceptions.FieldError(data['message'])
			elif(data['errorCode'] == 'MALFORMED_QUERY'):
				raise SyntaxError(data['message'])
			else:
				raise RuntimeError(str(data))
		
		body = response.body_string()
		response = force_unicode(body).encode(settings.DEFAULT_CHARSET)
		
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

string_literal = quoted_string_literal
conversions = {
	int: lambda s,d: str(s),
	long: lambda s,d: str(s),
	float: lambda o,d: '%.15g' % o,
	types.NoneType: lambda s,d: 'NULL',
	list: lambda s,d: '(%s)' % ','.join([escape_item(x, conversions) for x in s]),
	tuple: lambda s,d: '(%s)' % ','.join([escape_item(x, conversions) for x in s]),
	str: lambda o,d: string_literal(o, d), # default
	unicode: lambda s,d: string_literal(s.encode(), d),
	bool: lambda s,d: str(int(s)),
	datetime.date: lambda d,c: string_literal(date.strftime(d, "%Y-%m-%d"), c),
	datetime.datetime: lambda d,c: string_literal(date.strftime(d, "%Y-%m-%d %H:%M:%S"), c),
	datetime.timedelta: lambda v,c: string_literal('%d %d:%d:%d' % (v.days, int(v.seconds / 3600) % 24, int(v.seconds / 60) % 60, int(v.seconds) % 60)),
	decimal.Decimal: lambda s,d: str(s),
}
