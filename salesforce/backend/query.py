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

from django.conf import settings
from django.core import serializers, exceptions
from django.core.serializers import python, json as django_json
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.db.models import query
from django.db.models.sql import Query, constants, subqueries
from django.db.backends.signals import connection_created
from django.utils.encoding import force_unicode

import django
from pkg_resources import parse_version
DJANGO_14 = (parse_version(django.get_version()) >= parse_version('1.4'))

import restkit
import pytz

from salesforce import auth, models
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
		if(isinstance(item, models.SalesforceModel)):
			return conv.get(models.SalesforceModel, conv[str])(item, conv)
		if(isinstance(item, decimal.Decimal)):
			return conv.get(decimal.Decimal, conv[str])(item, conv)
		return conv.get(type(item), conv[str])(item, conv)
	return tuple([_escape(x, sql_conversions) for x in args])

def process_json_args(args):
	"""
	Perform necessary JSON quoting on the arg list.
	"""
	def _escape(item, conv):
		if(isinstance(item, models.SalesforceModel)):
			return conv.get(models.SalesforceModel, conv[str])(item, conv)
		if(isinstance(item, decimal.Decimal)):
			return conv.get(decimal.Decimal, conv[str])(item, conv)
		return conv.get(type(item), conv[str])(item, conv)
	return tuple([_escape(x, json_conversions) for x in args])

def handle_api_exceptions(url, f, *args, **kwargs):
	from salesforce.backend import base
	try:
		return f(*args, **kwargs)
	except restkit.ResourceNotFound, e:
		raise base.SalesforceError("Couldn't connect to API (404): %s" % e)
	except restkit.ResourceGone, e:
		raise base.SalesforceError("Couldn't connect to API (410): %s" % e)
	except restkit.Unauthorized, e:
		data = json.loads(str(e))[0]
		if(data['errorCode'] == 'INVALID_SESSION_ID'):
			auth.expire_token()
			auth.authenticate(settings.DATABASES[settings.SALESFORCE_DB_ALIAS])
			return f(*args, **kwargs)
		raise base.SalesforceError(str(e))
	except restkit.RequestFailed, e:
		data = json.loads(str(e))[0]
		if(data['errorCode'] == 'INVALID_FIELD'):
			raise base.SalesforceError(data['message'])
		elif(data['errorCode'] == 'MALFORMED_QUERY'):
			raise base.SalesforceError(data['message'])
		elif(data['errorCode'] == 'INVALID_FIELD_FOR_INSERT_UPDATE'):
			raise base.SalesforceError(data['message'])
		elif(data['errorCode'] == 'METHOD_NOT_ALLOWED'):
			raise base.SalesforceError('%s: %s' % (url, data['message']))
		# some kind of failed query
		else:
			raise base.SalesforceError(str(data))

def prep_for_deserialize(model, record, using):
	attribs = record.pop('attributes')
	
	mod = model.__module__.split('.')
	if(mod[-1] == 'models'):
		app_name = mod[-2]
	elif(hasattr(model._meta, 'app_name')):
		app_name = getattr(model._meta, 'app_name')
	else:
		raise ImproperlyConfigured("Can't discover the app_name for %s, you must specify it via model meta options.")
	
	fields = dict()
	for x in model._meta.fields:
		if not x.primary_key:
			field_val = record[x.column]
			db_type = x.db_type(connection=connections[using])
			if(x.__class__.__name__ == 'DateTimeField' and field_val is not None):
				d = datetime.datetime.strptime(field_val, SALESFORCE_DATETIME_FORMAT)
				import pytz
				d = d.replace(tzinfo=pytz.utc)
				fields[x.name] = d.strftime('%Y-%m-%d %H:%M:%S-00:00')
			else:
				fields[x.name] = field_val
	
	return dict(
		model	= '.'.join([app_name, model.__name__]),
		pk		= record.pop('Id'),
		fields	= fields,
	)

def extract_values(query):
	d = dict()
	fields = query.model._meta.fields
	for index in range(len(fields)):
		field = fields[index]
		if field.get_internal_type() == 'AutoField':
			continue
		if(isinstance(query, subqueries.UpdateQuery)):
			[bound_field] = [x for x in query.values if x[0].name == field.name]
			[arg] = process_json_args([bound_field[2]])
			d[bound_field[0].db_column or bound_field[0].name] = arg
		elif(DJANGO_14):
			[arg] = process_json_args([getattr(query.objs[0], field.name)])
			d[field.db_column or field.name] = arg
		else:
			[arg] = process_json_args([query.values[index][1]])
			d[field.db_column or field.name] = arg
	return d

def get_resource(url):
	salesforce_timeout = getattr(settings, 'SALESFORCE_QUERY_TIMEOUT', 3)
	resource = restkit.Resource(url, timeout=salesforce_timeout)
	log.debug('Request API URL: %s' % url)
	return resource

class SalesforceQuerySet(query.QuerySet):
	"""
	Use a custom SQL compiler to generate SOQL-compliant queries.
	"""
	def iterator(self):
		"""
		An iterator over the results from applying this QuerySet to the
		remote web service.
		"""
		sql, params = compiler.SQLCompiler(self.query, connections[self.db], None).as_sql()
		cursor = CursorWrapper(connections[self.db], self.query)
		cursor.execute(sql, params)
		
		def _prepare(data):
			for record in data:
				struct = prep_for_deserialize(self.model, record, self.db)
				yield struct
		
		response = cursor.fetchmany(constants.GET_ITERATOR_CHUNK_SIZE)
		if response is None:
			raise StopIteration
		
		for res in python.Deserializer(_prepare(response)):
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
		self.settings_dict = conn.settings_dict
		self.query = query
		self.results = iter([])
		self.rowcount = None
	
	@property
	def oauth(self):
		return auth.authenticate(self.settings_dict)
	
	def execute(self, q, args=None):
		"""
		Send a query to the Salesforce API.
		"""
		from salesforce.backend import base
		
		if(isinstance(self.query, SalesforceQuery)):
			response = self.execute_select(q, args)
		elif(isinstance(self.query, subqueries.InsertQuery)):
			response = self.execute_insert(self.query)
		elif(isinstance(self.query, subqueries.UpdateQuery)):
			response = self.execute_update(self.query)
		elif(isinstance(self.query, subqueries.DeleteQuery)):
			response = self.execute_delete(self.query)
		else:
			raise base.DatabaseError("Unsupported query: %s" % self.query)
		
		body = response.body_string()
		jsrc = force_unicode(body).encode(settings.DEFAULT_CHARSET)
		
		if(jsrc):
			data = json.loads(jsrc)
			# a SELECT query
			if('totalSize' in data):
				self.rowcount = data['totalSize']
			# a successful INSERT query, return after getting PK
			elif('success' in data and 'id' in data):
				self.lastrowid = data['id']
				return
			# something we don't recognize
			else:
				raise base.DatabaseError(data)
			
			if('count()' in q.lower()):
				# COUNT() queries in SOQL are a special case, as they don't actually return rows
				data['records'] = [{self.rowcount:'COUNT'}]
			
			self.results = (x for x in data['records'])
		else:
			self.results = []
	
	def execute_select(self, q, args):
		processed_sql = q % process_args(args)
		url = u'%s%s?%s' % (self.oauth['instance_url'], '%s/query' % API_STUB, urllib.urlencode(dict(
			q	= processed_sql,
		)))
		headers = dict(Authorization='OAuth %s' % self.oauth['access_token'])
		resource = get_resource(url)
		
		log.debug(processed_sql)
		return handle_api_exceptions(url, resource.get, headers=headers)
	
	def execute_insert(self, query):
		table = query.model._meta.db_table
		url = self.oauth['instance_url'] + API_STUB + ('/sobjects/%s/' % table)
		headers = dict()
		headers['Authorization'] = 'OAuth %s' % self.oauth['access_token']
		headers['Content-Type'] = 'application/json'
		post_data = extract_values(query)
		resource = get_resource(url)
		log.debug('INSERT %s%s' % (table, post_data))
		return handle_api_exceptions(url, resource.post, headers=headers, payload=json.dumps(post_data))
	
	def execute_update(self, query):
		table = query.model._meta.db_table
		# this will break in multi-row updates
		pk = query.where.children[0].children[0][-1]
		assert pk
		url = self.oauth['instance_url'] + API_STUB + ('/sobjects/%s/%s' % (table, pk))
		headers = dict()
		headers['Authorization'] = 'OAuth %s' % self.oauth['access_token']
		headers['Content-Type'] = 'application/json'
		post_data = extract_values(query)
		resource = get_resource(url)
		
		log.debug('UPDATE %s(%s)%s' % (table, pk, post_data))
		return handle_api_exceptions(url, resource.request, method='patch', headers=headers, payload=json.dumps(post_data))
	
	def execute_delete(self, query):
		table = query.model._meta.db_table
		# this will break in multi-row updates
		pk = self.query.where.children[0][-1][0]
		assert pk
		url = self.oauth['instance_url'] + API_STUB + ('/sobjects/%s/%s' % (table, pk))
		headers = dict()
		headers['Authorization'] = 'OAuth %s' % self.oauth['access_token']
		resource = get_resource(url)
		
		log.debug('DELETE %s(%s)' % (table, pk))
		return handle_api_exceptions(url, resource.delete, headers=headers)
	
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
		for index in range(constants.GET_ITERATOR_CHUNK_SIZE):
			try:
				row = self.fetchone()
				if(row is None):
					return result
				result.append(row)
			except StopIteration:
				pass
		return result

string_literal = quoted_string_literal
def date_literal(d, c):
	if(d.tzinfo):
		tzname = datetime.datetime.strftime(d, "%z").replace(':', '')
		return datetime.datetime.strftime(d, "%Y-%m-%dT%H:%M:%S.000") + tzname
	else:
		import time
		tz = pytz.timezone(settings.TIME_ZONE)
		nd = tz.localize(d, is_dst=time.daylight)
		tzname = datetime.datetime.strftime(nd, "%z").replace(':', '')
		return datetime.datetime.strftime(nd, "%Y-%m-%dT%H:%M:%S.000") + tzname

def sobj_id(obj, conv):
	return obj.pk

# supported types
sql_conversions = {
	int: lambda s,d: str(s),
	long: lambda s,d: str(s),
	float: lambda o,d: '%.15g' % o,
	types.NoneType: lambda s,d: 'NULL',
	str: lambda o,d: string_literal(o, d), # default
	unicode: lambda s,d: string_literal(s.encode('utf8'), d),
	bool: lambda s,d: str(s).lower(),
	datetime.date: lambda d,c: datetime.date.strftime(d, "%Y-%m-%d"),
	datetime.datetime: lambda d,c: date_literal(d, c),
	decimal.Decimal: lambda s,d: float(s),
	models.SalesforceModel: sobj_id,
}

# supported types
json_conversions = {
	int: lambda s,d: str(s),
	long: lambda s,d: str(s),
	float: lambda o,d: '%.15g' % o,
	types.NoneType: lambda s,d: None,
	str: lambda o,d: o, # default
	unicode: lambda s,d: s.encode('utf8'),
	bool: lambda s,d: str(s).lower(),
	datetime.date: lambda d,c: datetime.date.strftime(d, "%Y-%m-%d"),
	datetime.datetime: date_literal,
	decimal.Decimal: lambda s,d: float(s),
	models.SalesforceModel: sobj_id,
}
