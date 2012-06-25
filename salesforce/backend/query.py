# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

"""
Salesforce object query customizations.
"""

import copy, urllib, logging, types, datetime, decimal

from django.core import serializers, exceptions
from django.conf import settings
from django.db.models import query
from django.db.models.sql import Query, constants
from django.utils.encoding import force_unicode
from django.db.backends.signals import connection_created
from django.core.serializers import python, json as django_json
from django.core.exceptions import ImproperlyConfigured

import restkit
import pytz

from salesforce import auth
from salesforce.backend import compiler

try:
	import json
except ImportError, e:
	import simplejson as json

log = logging.getLogger(__name__)

API_STUB = '/services/data/v24.0'
SALESFORCE_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.000+0000'

def quoted_string_literal(s, d):
	"""
	According to the SQL standard, this should be all you need to do to escape any kind of string.
	"""
	try:
		return "'%s'" % (s.replace("'", "''"),)
	except TypeError, e:
		raise NotImplementedError("Cannot quote %r objects: %r" % (type(s), s))

def process_args(args):
	"""
	Perform necessary quoting on the arg list.
	"""
	def _escape(item, conv):
		return conv.get(type(item), conv[str])(item, conv)
	return tuple([_escape(x, sql_conversions) for x in args])

def process_json_args(args):
	"""
	Perform necessary JSON quoting on the arg list.
	"""
	def _escape(item, conv):
		return conv.get(type(item), conv[str])(item, conv)
	return tuple([_escape(x, json_conversions) for x in args])

def handle_api_exceptions(f, *args, **kwargs):
	from salesforce.backend import base
	try:
		return f(*args, **kwargs)
	except restkit.ResourceNotFound, e:
		raise base.SalesforceError("Couldn't connect to API (404): %s" % e)
	except restkit.ResourceGone, e:
		raise base.SalesforceError("Couldn't connect to API (410): %s" % e)
	except restkit.Unauthorized, e:
		raise exceptions.PermissionDenied(str(e))
	except restkit.RequestFailed, e:
		data = json.loads(str(e))[0]
		if(data['errorCode'] == 'INVALID_FIELD'):
			raise base.SalesforceError(data['message'])
		elif(data['errorCode'] == 'MALFORMED_QUERY'):
			raise base.SalesforceError(data['message'])
		elif(data['errorCode'] == 'INVALID_FIELD_FOR_INSERT_UPDATE'):
			raise base.SalesforceError(data['message'])
		elif(data['errorCode'] == 'METHOD_NOT_ALLOWED'):
			raise base.SalesforceError("[%s] %s" % (url, data['message']))
		else:
			raise base.SalesforceError(str(data))

class SalesforceQuerySet(query.QuerySet):
	"""
	Use a custom SQL compiler to generate SOQL-compliant queries.
	"""
	def iterator(self):
		"""
		An iterator over the results from applying this QuerySet to the
		remote web service.
		"""
		from django.db import connections
		sql, params = compiler.SQLCompiler(self.query, connections[self.db], None).as_sql()
		cursor = CursorWrapper(connections[self.db], self.query)
		cursor.execute(sql, params)
		
		def _mkmodels(data):
			for record in data:
				attribs = record.pop('attributes')
				
				mod = self.model.__module__.split('.')
				if(mod[-1] == 'models'):
					app_name = mod[-2]
				elif(hasattr(self.model._meta, 'app_name')):
					app_name = getattr(self.model._meta, 'app_name')
				else:
					raise ImproperlyConfigured("Can't discover the app_name for %s, you must specify it via model meta options.")
				
				fields = dict()
				for x in self.model._meta.fields:
					if not x.primary_key:
						field_val = record[x.column]
						db_type = x.db_type(connection=connections[self.db])
						if(x.__class__.__name__ == 'DateTimeField' and field_val is not None):
							d = datetime.datetime.strptime(field_val, SALESFORCE_DATETIME_FORMAT)
							fields[x.name] = d.strftime('%Y-%m-%d %H:%M:%S')
						else:
							fields[x.name] = field_val
				
				yield dict(
					model	= '.'.join([app_name, self.model.__name__]),
					pk		= record.pop('Id'),
					fields	= fields,
				)
		
		response = cursor.fetchmany(constants.GET_ITERATOR_CHUNK_SIZE)
		if response is None:
			raise StopIteration
		for res in python.Deserializer(_mkmodels(response)):
			yield res.object

class SalesforceQuery(Query):
	"""
	Override aggregates.
	"""
	from salesforce.backend import aggregates
	aggregates_module = aggregates
	
	def has_results(self, using):
		q = self.clone()
		compiler = q.get_compiler(using=using)
		return bool(compiler.execute_sql(constants.SINGLE))

class CursorWrapper(object):
	"""
	A wrapper that emulates the behavior of a database cursor.
	
	This is the class that is actually responsible for making connections
	to the SF REST API
	"""
	def __init__(self, conn, query=None):
		"""
		Connect to the Salesforce API.
		"""
		connection_created.send(sender=self.__class__, connection=self)
		self.oauth = auth.authenticate(conn.settings_dict)
		self.query = query
		self.results = iter([])
		self.rowcount = None
	
	def execute(self, q, args=None):
		"""
		Send a query to the Salesforce API.
		"""
		from salesforce.backend import base
		
		headers = dict()
		headers['Authorization'] = 'OAuth %s' % self.oauth['access_token']
		
		def _extract_values(method):
			d = dict()
			for x in self.query.values:
				if x[0].get_internal_type() == 'AutoField':
					continue
				[arg] = process_json_args([x[[2,1][method=='insert']]])
				d[x[0].db_column or x[0].name] = arg
			return d
		
		processed_sql = q % process_args(args)
		log.debug(processed_sql)
		url = None
		post_data = dict()
		table = self.query.model._meta.db_table
		
		if(q.upper().startswith('SELECT')):
			method = 'query'
			url = u'%s%s?%s' % (self.oauth['instance_url'], '%s/query' % API_STUB, urllib.urlencode(dict(
				q	= processed_sql,
			)))
		elif(q.upper().startswith('INSERT')):
			method = 'insert'
			url = self.oauth['instance_url'] + API_STUB + ('/sobjects/%s/' % table)
			post_data = _extract_values(method)
			headers['Content-Type'] = 'application/json'
		elif(q.upper().startswith('UPDATE')):
			method = 'update'
			# this will break in multi-row updates
			pk = self.query.where.children[0].children[0][-1]
			url = self.oauth['instance_url'] + API_STUB + ('/sobjects/%s/%s' % (table, pk))
			post_data = _extract_values(method)
			headers['Content-Type'] = 'application/json'
		elif(q.upper().startswith('DELETE')):
			method = 'delete'
			# this will break in multi-row updates
			pk = self.query.where.children[0][-1][0]
			url = self.oauth['instance_url'] + API_STUB + ('/sobjects/%s/%s' % (table, pk))
		else:
			raise base.DatabaseError("Unsupported query: %s" % debug_sql)
		
		salesforce_timeout = getattr(settings, 'SALESFORCE_QUERY_TIMEOUT', 3)
		resource = restkit.Resource(url, timeout=salesforce_timeout)
		log.debug('Request API URL: %s' % url)
		
		if(method == 'query'):
			response = handle_api_exceptions(resource.get, headers=headers)
		elif(method == 'insert'):
			response = handle_api_exceptions(resource.post, headers=headers, payload=json.dumps(post_data))
		elif(method == 'delete'):
			response = handle_api_exceptions(resource.delete, headers=headers)
		else:#(method == 'update')
			response = handle_api_exceptions(resource.request, method='patch', headers=headers, payload=json.dumps(post_data))
		
		body = response.body_string()
		jsrc = force_unicode(body).encode(settings.DEFAULT_CHARSET)
		
		try:
			data = json.loads(jsrc)
		except Exception, e:
			if(method not in ('delete', 'update')):
				raise e
			else:
				data = []
		
		if('totalSize' in data):
			self.rowcount = data['totalSize']
		elif('errorCode' in data):
			raise base.DatabaseError(data['message'])
		elif(method == 'insert'):
			if(data['success']):
				self.lastrowid = data['id']
			else:
				raise base.DatabaseError(data['errors'])
		
		if('count()' in q.lower()):
			# COUNT() queries in SOQL are a special case, as they don't actually return rows
			data['records'] = [{self.rowcount:'COUNT'}]
		
		def _iterate(d):
			for record in d['records']:
				yield record
		
		self.results = _iterate(data)
	
	def fetchone(self):
		"""
		Fetch a single result from a previously executed query.
		"""
		try:
			res = self.results.next()
			return res
		except StopIteration:
			return None
	
	def fetchmany(self, size=0):
		"""
		Fetch multiple results from a previously executed query.
		"""
		result = None
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
				result = [] if result is None else result
				result.append(row)
			except StopIteration:
				pass
		return result

	def fetchall(self):
		"""
		Fetch all results from a previously executed query.
		"""
		result = []
		for index in range(size):
			try:
				row = self.fetchone()
				if(row is None):
					return None
				result.append(row)
			except StopIteration:
				pass
		return result

string_literal = quoted_string_literal
def date_literal(d, c):
	import time
	tz = pytz.timezone(settings.TIME_ZONE)
	nd = tz.localize(d, is_dst=time.daylight)
	tzname = datetime.datetime.strftime(nd, "%z").replace(':', '')
	return datetime.datetime.strftime(nd, "%Y-%m-%dT%H:%M:%S.000") + tzname

# supported types
sql_conversions = {
	int: lambda s,d: str(s),
	long: lambda s,d: str(s),
	float: lambda o,d: '%.15g' % o,
	types.NoneType: lambda s,d: 'NULL',
	str: lambda o,d: string_literal(o, d), # default
	unicode: lambda s,d: string_literal(s.encode(), d),
	bool: lambda s,d: str(s).lower(),
	datetime.date: lambda d,c: string_literal(datetime.date.strftime(d, "%Y-%m-%d"), c),
	datetime.datetime: lambda d,c: string_literal(date_literal(d, c), c),
	datetime.timedelta: lambda v,c: string_literal('%d %d:%d:%d' % (v.days, int(v.seconds / 3600) % 24, int(v.seconds / 60) % 60, int(v.seconds) % 60)),
	decimal.Decimal: lambda s,d: str(s),
}

# supported types
json_conversions = {
	int: lambda s,d: str(s),
	long: lambda s,d: str(s),
	float: lambda o,d: '%.15g' % o,
	types.NoneType: lambda s,d: None,
	str: lambda o,d: o, # default
	unicode: lambda s,d: s.encode(),
	bool: lambda s,d: str(s).lower(),
	datetime.date: lambda d,c: datetime.date.strftime(d, "%Y-%m-%d"),
	datetime.datetime: date_literal,
	datetime.timedelta: lambda v,c: '%d %d:%d:%d' % (v.days, int(v.seconds / 3600) % 24, int(v.seconds / 60) % 60, int(v.seconds) % 60),
	decimal.Decimal: lambda s,d: str(s),
}
