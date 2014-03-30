# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce object query customizations.
"""

import logging, types, datetime, decimal

from django.conf import settings
from django.core.serializers import python
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.db.models import query
from django.db.models.sql import Query, RawQuery, constants, subqueries
from django.utils.encoding import force_text
from django.utils.six import PY3

from itertools import islice

import requests
import pytz

from salesforce import auth, models, DJANGO_16, DJANGO_17_PLUS
from salesforce.backend import compiler, sf_alias
from salesforce.fields import NOT_UPDATEABLE, NOT_CREATEABLE

try:
	from urllib.parse import urlencode
except ImportError:
	from urllib import urlencode
try:
	import json
except ImportError:
	import simplejson as json

log = logging.getLogger(__name__)

API_STUB = '/services/data/v28.0'

# Values of seconds are with 3 decimal places in SF, but they are rounded to
# whole seconds for the most of fields.
SALESFORCE_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f+0000'
DJANGO_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f-00:00'

def quoted_string_literal(s, d):
	"""
	SOQL requires single quotes to be escaped.
	http://www.salesforce.com/us/developer/docs/soql_sosl/Content/sforce_api_calls_soql_select_quotedstringescapes.htm
	"""
	try:
		return "'%s'" % (s.replace("'", "\\'"),)
	except TypeError as e:
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

def reauthenticate():
	auth.expire_token()
	oauth = auth.authenticate(settings.DATABASES[sf_alias])
	return oauth['access_token']

def handle_api_exceptions(url, f, *args, **kwargs):
	"""Call REST API and handle exceptions
	Params:  f:  requests.get or requests.post...
	"""
	from salesforce.backend import base
	kwargs_in = {'timeout': getattr(settings, 'SALESFORCE_QUERY_TIMEOUT', 3)}
	kwargs_in.update(kwargs)
	log.debug('Request API URL: %s' % url)
	try:
		response = f(url, *args, **kwargs_in)
		if response.status_code in (200, 201, 204):
			return response
	except requests.exceptions.Timeout:
		raise base.SalesforceError("Timeout, URL=%s" % url)
	else:
		# TODO Remove this print after tuning of specific messages. Currently is
		#      better more than less
		print("Error (debug details) %s\n%s" % (response.text, response.__dict__))
		if response.status_code >= 400:
			if response.status_code == 404:  # ResourceNotFound
				raise base.SalesforceError("Couldn't connect to API (404): %s, URL=%s"
						% (response.text, url))
			if response.status_code in (401, 403):  # Unauthorized
				data = response.json()[0]
				if(data['errorCode'] == 'INVALID_SESSION_ID'):
					token = reauthenticate()
					if('headers' in kwargs):
						kwargs['headers'].update(dict(Authorization='OAuth %s' % token))
					return f(url, *args, **kwargs)
				raise base.SalesforceError(response.text)
			# TODO remove: According to SF docs: The status code 410 is unused by SF.
			if response.status_code == 410:  # ResourceGone
				raise base.SalesforceError("Couldn't connect to API (410): %s" % response.text)
			else:   # RequestFailed
				data = response.json()[0]
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
					raise base.SalesforceError('%s' % data)

def prep_for_deserialize(model, record, using):
	attribs = record.pop('attributes')

	mod = model.__module__.split('.')
	if(mod[-1] == 'models'):
		app_label = mod[-2]
	elif(hasattr(model._meta, 'app_label')):
		app_label = getattr(model._meta, 'app_label')
	else:
		raise ImproperlyConfigured("Can't discover the app_label for %s, you must specify it via model meta options.")

	fields = dict()
	for x in model._meta.fields:
		if not x.primary_key:
			field_val = record[x.column]
			db_type = x.db_type(connection=connections[using])
			if(x.__class__.__name__ == 'DateTimeField' and field_val is not None):
				d = datetime.datetime.strptime(field_val, SALESFORCE_DATETIME_FORMAT)
				import pytz
				d = d.replace(tzinfo=pytz.utc)
				fields[x.name] = d.strftime(DJANGO_DATETIME_FORMAT)
			else:
				fields[x.name] = field_val

	return dict(
		model	= '.'.join([app_label, model.__name__]),
		pk		= record.pop('Id'),
		fields	= fields,
	)

def extract_values(query):
	"""
	Extract values from insert or update query.
	"""
	d = dict()
	fields = query.model._meta.fields
	for index in range(len(fields)):
		field = fields[index]
		if (field.get_internal_type() == 'AutoField' or
				isinstance(query, subqueries.UpdateQuery) and (getattr(field, 'sf_read_only', 0) & NOT_UPDATEABLE) != 0 or
				isinstance(query, subqueries.InsertQuery) and (getattr(field, 'sf_read_only', 0) & NOT_CREATEABLE) != 0):
			continue
		if(isinstance(query, subqueries.UpdateQuery)):
			value_or_empty = [value for qfield, model, value in query.values if qfield.name == field.name]
			if value_or_empty:
				[value] = value_or_empty
			else:
				assert len(query.values) < len(fields), \
						"Match name can miss only with an 'update_fields' argument."
				continue
		else:  # insert
			assert len(query.objs) == 1, "bulk_create is not supported by Salesforce backend."
			value = getattr(query.objs[0], field.attname)
			if isinstance(field, models.ForeignKey) and value == 'DEFAULT':
				continue
		[arg] = process_json_args([value])
		d[field.db_column or field.name] = arg
	return d

class SalesforceRawQuerySet(query.RawQuerySet):
	def __len__(self):
		if(self.query.cursor is None):
			# force the query
			self.query.get_columns()
			return len(self.query.cursor.results)
		else:
			return 0;

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

		pfd = prep_for_deserialize
		for res in python.Deserializer(pfd(self.model, r, self.db) for r in cursor.results):
			yield res.object

class SalesforceRawQuery(RawQuery):
	def clone(self, using):
		return SalesforceRawQuery(self.sql, using, params=self.params)

	def get_columns(self):
		if self.cursor is None:
			self._execute_query()
		converter = connections[self.using].introspection.table_name_converter
		if(len(self.cursor.results) > 0):
			return [converter(col) for col in self.cursor.results[0].keys() if col != 'attributes']
		return ['Id']

	def _execute_query(self):
		self.cursor = CursorWrapper(connections[self.using], self)
		self.cursor.execute(self.sql, self.params)

	def __repr__(self):
		return "<SalesforceRawQuery: %r>" % (self.sql % tuple(self.params))

class SalesforceQuery(Query):
	"""
	Override aggregates.
	"""
	# Warn against name collision: The name 'aggregates' is the name of
	# a new property introduced by Django 1.7 to the parent class
	# 'django.db.models.sql.query.Query'.
	from salesforce.backend import aggregates as aggregates_module

	def clone(self, klass=None, memo=None, **kwargs):
		return Query.clone(self, klass, memo, **kwargs)

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
	def __init__(self, connection, query=None):
		"""
		Connect to the Salesforce API.
		"""
		self.settings_dict = connection.settings_dict
		self.connection = connection
		self.session = connection.sf_session
		self.query = query
		self.results = []
		self.rowcount = None

	@property
	def oauth(self):
		return auth.authenticate(self.settings_dict)

	def execute(self, q, args=None):
		"""
		Send a query to the Salesforce API.
		"""
		from salesforce.backend import base

		self.rowcount = None
		if(isinstance(self.query, SalesforceQuery)):
			response = self.execute_select(q, args)
		elif(isinstance(self.query, SalesforceRawQuery)):
			response = self.execute_select(q, args)
		elif(isinstance(self.query, subqueries.InsertQuery)):
			response = self.execute_insert(self.query)
		elif(isinstance(self.query, subqueries.UpdateQuery)):
			response = self.execute_update(self.query)
		elif(isinstance(self.query, subqueries.DeleteQuery)):
			response = self.execute_delete(self.query)
		else:
			raise base.DatabaseError("Unsupported query: %s" % self.query)

		# the encoding is detected automatically, e.g. from headers
		if(response and response.text):
			# parse_float set to decimal.Decimal to avoid precision errors when
			# converting from the json number to a float to a Decimal object
			# on a model's DecimalField...converts from json number directly
			# a Decimal object
			data = response.json(parse_float=decimal.Decimal)
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

			if q.upper().startswith('SELECT COUNT() FROM'):
				# TODO what about raw query COUNT()
				# COUNT() queries in SOQL are a special case, as they don't actually return rows
				self.results = [[self.rowcount]]
			else:
				self.results = self.query_results(data)
		else:
			self.results = []

	def execute_select(self, q, args):
		processed_sql = str(q) % process_args(args)
		url = u'%s%s?%s' % (self.oauth['instance_url'], '%s/query' % API_STUB, urlencode(dict(
			q	= processed_sql,
		)))
		log.debug(processed_sql)
		return handle_api_exceptions(url, self.session.get)

	def query_more(self, nextRecordsUrl):
		url = u'%s%s' % (self.oauth['instance_url'], nextRecordsUrl)
		return handle_api_exceptions(url, self.session.get)

	def execute_insert(self, query):
		table = query.model._meta.db_table
		url = self.oauth['instance_url'] + API_STUB + ('/sobjects/%s/' % table)
		headers = {'Content-Type': 'application/json'}
		post_data = extract_values(query)

		log.debug('INSERT %s%s' % (table, post_data))
		return handle_api_exceptions(url, self.session.post, headers=headers, data=json.dumps(post_data))

	def execute_update(self, query):
		table = query.model._meta.db_table
		# this will break in multi-row updates
		if DJANGO_17_PLUS:
			pk = query.where.children[0].rhs
		elif DJANGO_16:
			pk = query.where.children[0][3]
		else:
			pk = query.where.children[0].children[0][-1]
		assert pk
		url = self.oauth['instance_url'] + API_STUB + ('/sobjects/%s/%s' % (table, pk))
		headers = {'Content-Type': 'application/json'}
		post_data = extract_values(query)
		log.debug('UPDATE %s(%s)%s' % (table, pk, post_data))
		ret = handle_api_exceptions(url, self.session.patch, headers=headers, data=json.dumps(post_data))
		self.rowcount = 1
		return ret

	def execute_delete(self, query):
		table = query.model._meta.db_table
		## the root where node's children may itself have children..
		def recurse_for_pk(children):
			for node in children:
				if hasattr(node, 'rhs'):
					pk = node.rhs[0]  # for Django 1.7+
				else:
					try:
						pk = node[-1][0]
					except TypeError:
						pk = recurse_for_pk(node.children)
				return pk
		pk = recurse_for_pk(self.query.where.children)
		assert pk
		url = self.oauth['instance_url'] + API_STUB + ('/sobjects/%s/%s' % (table, pk))

		log.debug('DELETE %s(%s)' % (table, pk))
		return handle_api_exceptions(url, self.session.delete)

	def query_results(self, results):
		output = []
		while True:
			for rec in results['records']:
				if rec['attributes']['type'] == 'AggregateResult':
					assert len(rec) -1 == len(list(self.query.aggregate_select.items()))
					# The 'attributes' info is unexpected for Django within fields.
					rec = [rec[k] for k, _ in self.query.aggregate_select.items()]
				output.append(rec)

			if results['done']:
				break
			# see about Retrieving the Remaining SOQL Query Results
			# http://www.salesforce.com/us/developer/docs/api_rest/Content/dome_query.htm#heading_2_1
			response = self.query_more(results['nextRecordsUrl'])
			results = response.json(parse_float=decimal.Decimal)
		return output

	def __iter__(self):
		return iter(self.results)

	def fetchone(self):
		"""
		Fetch a single result from a previously executed query.
		"""
		try:
			return self.results.pop(0)
		except StopIteration:
			return None

	def fetchmany(self, size=0):
		"""
		Fetch multiple results from a previously executed query.
		"""
		return list(islice(self.results, size))

	def fetchall(self):
		"""
		Fetch all results from a previously executed query.
		"""
		return list(self.results)

	def close(self):  # for Django 1.7+
		pass

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
	float: lambda o,d: '%.15g' % o,
	type(None): lambda s,d: 'NULL',
	str: lambda o,d: string_literal(o, d), # default
	bool: lambda s,d: str(s).lower(),
	datetime.date: lambda d,c: datetime.date.strftime(d, "%Y-%m-%d"),
	datetime.datetime: lambda d,c: date_literal(d, c),
	decimal.Decimal: lambda s,d: float(s),
	models.SalesforceModel: sobj_id,
}
if not PY3:
	sql_conversions[long] = lambda s,d: str(s)
	sql_conversions[unicode] = lambda s,d: string_literal(s.encode('utf8'), d)

# supported types
json_conversions = {
	int: lambda s,d: str(s),
	float: lambda o,d: '%.15g' % o,
	type(None): lambda s,d: None,
	str: lambda o,d: o, # default
	bool: lambda s,d: str(s).lower(),
	datetime.date: lambda d,c: datetime.date.strftime(d, "%Y-%m-%d"),
	datetime.datetime: date_literal,
	datetime.time: lambda d,c: datetime.time.strftime(d, "%H:%M:%S.%f"),
	decimal.Decimal: lambda s,d: float(s),
	models.SalesforceModel: sobj_id,
}
if not PY3:
	json_conversions[long] = lambda s,d: str(s)
	json_conversions[unicode] = lambda s,d: s.encode('utf8')
