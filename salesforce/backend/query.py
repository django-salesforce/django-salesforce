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
from django.db.models import query, Count
from django.db.models.sql import Query, RawQuery, constants, subqueries
from django.db.models.query_utils import deferred_class_factory
from django.utils.encoding import force_text
from django.utils.six import PY3

from itertools import islice

import requests
import pytz

from salesforce import auth, models, DJANGO_16_PLUS, DJANGO_17_PLUS, DJANGO_18_PLUS
from salesforce.backend import compiler, sf_alias
from salesforce.fields import NOT_UPDATEABLE, NOT_CREATEABLE, SF_PK

try:
	from urllib.parse import urlencode
except ImportError:
	from urllib import urlencode
try:
	import json
except ImportError:
	import simplejson as json

log = logging.getLogger(__name__)

API_STUB = '/services/data/v32.0'

# Values of seconds are with 3 decimal places in SF, but they are rounded to
# whole seconds for the most of fields.
SALESFORCE_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f+0000'
DJANGO_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f-00:00'

request_count = 0

def quoted_string_literal(s, d):
	"""
	SOQL requires single quotes to be escaped.
	http://www.salesforce.com/us/developer/docs/soql_sosl/Content/sforce_api_calls_soql_select_quotedstringescapes.htm
	"""
	try:
		return "'%s'" % (s.replace("\\", "\\\\").replace("'", "\\'"),)
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

def handle_api_exceptions(url, f, *args, **kwargs):
	"""Call REST API and handle exceptions
	Params:
		f:  requests.get or requests.post...
		_cursor: sharing the debug information in cursor
	"""
	global request_count 
	from salesforce.backend import base
	kwargs_in = {'timeout': getattr(settings, 'SALESFORCE_QUERY_TIMEOUT', 3),
				 'verify': True}
	kwargs_in.update(kwargs)
	_cursor = kwargs_in.pop('_cursor', None)
	log.debug('Request API URL: %s' % url)
	request_count += 1
	try:
		response = f(url, *args, **kwargs_in)
	# TODO some timeouts can be rarely raised as "SSLError: The read operation timed out"
	except requests.exceptions.Timeout:
		raise base.SalesforceError("Timeout, URL=%s" % url)
	if response.status_code == 401:
		# Unauthorized (expired or invalid session ID or OAuth)
		data = response.json()[0]
		if(data['errorCode'] == 'INVALID_SESSION_ID'):
			token = auth.reauthenticate(db_alias=f.__self__.auth.db_alias)
			if('headers' in kwargs):
				kwargs['headers'].update(dict(Authorization='OAuth %s' % token))
			try:
				response = f(url, *args, **kwargs_in)
			except requests.exceptions.Timeout:
				raise base.SalesforceError("Timeout, URL=%s" % url)

	if response.status_code in (200, 201, 204):
		return response

	# TODO Remove this verbose setting after tuning of specific messages.
	#      Currently it is better more or less.
	# http://www.salesforce.com/us/developer/docs/api_rest/Content/errorcodes.htm
	verbose = not getattr(getattr(_cursor, 'query', None), 'debug_silent', False)
	# Errors are reported in the body
	data = response.json()[0]
	if response.status_code == 404:  # ResourceNotFound
		if (f.__func__.__name__ == 'delete') and data['errorCode'] in (
				'ENTITY_IS_DELETED', 'INVALID_CROSS_REFERENCE_KEY'):
			# It is a delete command and the object is in trash bin or
			# completely deleted or it only could be a valid Id for this type
			# then is ignored similarly to delete by a classic database query:
			# DELETE FROM xy WHERE id = 'something_deleted_yet'
			return None
		else:
			# if this Id can not be ever valid.
			raise base.SalesforceError("Couldn't connect to API (404): %s, URL=%s"
					% (response.text, url), data, response, verbose)
	if(data['errorCode'] == 'INVALID_FIELD'):
		raise base.SalesforceError(data['message'], data, response, verbose)
	elif(data['errorCode'] == 'MALFORMED_QUERY'):
		raise base.SalesforceError(data['message'], data, response, verbose)
	elif(data['errorCode'] == 'INVALID_FIELD_FOR_INSERT_UPDATE'):
		raise base.SalesforceError(data['message'], data, response, verbose)
	elif(data['errorCode'] == 'METHOD_NOT_ALLOWED'):
		raise base.SalesforceError('%s: %s' % (url, data['message']), data, response, verbose)
	# some kind of failed query
	else:
		raise base.SalesforceError('%s' % data, data, response, verbose)

def prep_for_deserialize(model, record, using, init_list=None):
	"""
	Convert a record from SFDC (decoded JSON) to dict(model string, pk, fields)
	If fixes fields of some types. If names of required fields `init_list `are
	specified, then only these fields are processed.
	"""
	from salesforce.backend import base
	# TODO the parameter 'using' is not currently important.
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
		if not x.primary_key and (not init_list or x.name in init_list):
			if x.column.endswith('.Type'):
				# Type of generic foreign key
				simple_column, _ = x.column.split('.')
				fields[x.name] = record[simple_column]['Type']
			else:
				# Normal fields
				field_val = record[x.column]
				#db_type = x.db_type(connection=connections[using])
				if(x.__class__.__name__ == 'DateTimeField' and field_val is not None):
					d = datetime.datetime.strptime(field_val, SALESFORCE_DATETIME_FORMAT)
					import pytz
					d = d.replace(tzinfo=pytz.utc)
					if settings.USE_TZ:
						fields[x.name] = d.strftime(DJANGO_DATETIME_FORMAT)
					else:
						tz = pytz.timezone(settings.TIME_ZONE)
						d = tz.normalize(d.astimezone(tz))
						fields[x.name] = d.strftime(DJANGO_DATETIME_FORMAT[:-6])
				else:
					fields[x.name] = field_val
	if init_list and set(init_list).difference(fields).difference([SF_PK]):
		raise base.DatabaseError("Not found some expected fields")

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
			# TODO bulk insert
			assert len(query.objs) == 1, "bulk_create is not supported by Salesforce REST API"
			value = getattr(query.objs[0], field.attname)
			# The 'DEFAULT' is a backward compatibility name.
			if isinstance(field, models.ForeignKey) and value in ('DEFAULT', 'DEFAULTED_ON_CREATE'):
				continue
			if isinstance(value, models.DefaultedOnCreate):
				continue
		[arg] = process_json_args([value])
		d[field.column] = arg
	return d

class SalesforceRawQuerySet(query.RawQuerySet):
	def __len__(self):
		if self.query.cursor is None:
			# force the query
			self.query.get_columns()
		return self.query.cursor.rowcount

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

		only_load = self.query.get_loaded_field_names()
		load_fields = []
		# If only/defer clauses have been specified,
		# build the list of fields that are to be loaded.
		if not only_load:
			model_cls = self.model
			init_list = None
		else:
			if DJANGO_16_PLUS:
				fields = self.model._meta.concrete_fields
				fields_with_model = self.model._meta.get_concrete_fields_with_model()
			else:
				fields = self.model._meta.fields
				fields_with_model = self.model._meta.get_fields_with_model()
			for field, model in fields_with_model:
				if model is None:
					model = self.model
				try:
					if field.name in only_load[model]:
						# Add a field that has been explicitly included
						load_fields.append(field.name)
				except KeyError:
					# Model wasn't explicitly listed in the only_load table
					# Therefore, we need to load all fields from this model
					load_fields.append(field.name)

			init_list = []
			skip = set()
			for field in fields:
				if field.name not in load_fields:
					skip.add(field.attname)
				else:
					init_list.append(field.name)
			model_cls = deferred_class_factory(self.model, skip)

		field_names = self.query.get_loaded_field_names()
		for res in python.Deserializer(pfd(model_cls, r, self.db, init_list) for r in cursor.results):
			# Store the source database of the object
			res.object._state.db = self.db
			# This object came from the database; it's not being added.
			res.object._state.adding = False
			yield res.object

	def query_all(self):
		"""
		Allows querying for also deleted or merged records.
			Lead.objects.query_all().filter(IsDeleted=True,...)
		https://www.salesforce.com/us/developer/docs/api_rest/Content/resources_queryall.htm
		"""
		obj = self._clone(klass=SalesforceQuerySet)
		obj.query.set_query_all()
		return obj

class SalesforceRawQuery(RawQuery):
	def clone(self, using):
		return SalesforceRawQuery(self.sql, using, params=self.params)

	def get_columns(self):
		if self.cursor is None:
			self._execute_query()
		converter = connections[self.using].introspection.table_name_converter
		if self.cursor.rowcount > 0:
			return [converter(col) for col in self.cursor.first_row.keys() if col != 'attributes']
		return ['Id']

	def _execute_query(self):
		self.cursor = CursorWrapper(connections[self.using], self)
		self.cursor.execute(self.sql, self.params)

	def __repr__(self):
		return "<SalesforceRawQuery: %s; %r>" % (self.sql, tuple(self.params))

class SalesforceQuery(Query):
	"""
	Override aggregates.
	"""
	# Warn against name collision: The name 'aggregates' is the name of
	# a new property introduced by Django 1.7 to the parent class
	# 'django.db.models.sql.query.Query'.
	# 'aggregates_module' is overriden here, to be visible in the base class.
	from salesforce.backend import aggregates as aggregates_module

	def __init__(self, *args, **kwargs):
		super(SalesforceQuery, self).__init__(*args, **kwargs)
		self.is_query_all = False
		self.first_chunk_len = None
		self.max_depth = 1

	def clone(self, klass=None, memo=None, **kwargs):
		query = Query.clone(self, klass, memo, **kwargs)
		query.is_query_all = self.is_query_all
		return query

	def has_results(self, using):
		q = self.clone()
		compiler = q.get_compiler(using=using)
		return bool(compiler.execute_sql(constants.SINGLE))

	def set_query_all(self):
		self.is_query_all = True

	if DJANGO_18_PLUS:
		def get_count(self, using):
			"""
			Performs a COUNT() query using the current filter constraints.
			"""
			obj = self.clone()
			obj.add_annotation(Count('pk'), alias='x_sf_count', is_summary=True)
			number = obj.get_aggregation(using, ['x_sf_count'])['x_sf_count']
			if number is None:
				number = 0
			return number


class CursorWrapper(object):
	"""
	A wrapper that emulates the behavior of a database cursor.

	This is the class that is actually responsible for making connections
	to the SF REST API
	"""
	def __init__(self, db, query=None):
		"""
		Connect to the Salesforce API.
		"""
		self.db = db
		self.query = query
		self.session = db.sf_session
		# A consistent value of empty self.results after execute will be `iter([])`
		self.results = None
		self.rowcount = None
		self.first_row = None

	def __enter__(self):
		return self

	def __exit__(self, type, value, traceback):
		self.close()

	@property
	def oauth(self):
		return auth.authenticate(db_alias=self.db.alias)

	def execute(self, q, args=()):
		"""
		Send a query to the Salesforce API.
		"""
		from salesforce.backend import base

		self.rowcount = None
		if isinstance(self.query, SalesforceQuery) or self.query is None:
			response = self.execute_select(q, args)
		elif isinstance(self.query, SalesforceRawQuery):
			response = self.execute_select(q, args)
		elif isinstance(self.query, subqueries.InsertQuery):
			response = self.execute_insert(self.query)
		elif isinstance(self.query, subqueries.UpdateQuery):
			response = self.execute_update(self.query)
		elif isinstance(self.query, subqueries.DeleteQuery):
			response = self.execute_delete(self.query)
		else:
			raise base.DatabaseError("Unsupported query: type %s: %s" % (type(self.query), self.query))

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
				# COUNT() queries in SOQL are a special case, as they don't actually return rows
				self.results = iter([[self.rowcount]])
			else:
				if self.query:
					self.query.first_chunk_len = len(data['records'])
				self.first_row = data['records'][0] if data['records'] else None
				self.results = self.query_results(data)
		else:
			self.results = iter([])

	def execute_select(self, q, args):
		processed_sql = str(q) % process_args(args)
		cmd = 'query' if not getattr(self.query, 'is_query_all', False) else 'queryAll'
		url = u'{base}{api}/{cmd}?{query_str}'.format(
				base=self.session.auth.instance_url, api=API_STUB, cmd=cmd,
				query_str=urlencode(dict(q=processed_sql)),
		)
		log.debug(processed_sql)
		return handle_api_exceptions(url, self.session.get, _cursor=self)

	def query_more(self, nextRecordsUrl):
		url = u'%s%s' % (self.session.auth.instance_url, nextRecordsUrl)
		return handle_api_exceptions(url, self.session.get, _cursor=self)

	def execute_insert(self, query):
		table = query.model._meta.db_table
		url = self.session.auth.instance_url + API_STUB + ('/sobjects/%s/' % table)
		headers = {'Content-Type': 'application/json'}
		post_data = extract_values(query)

		log.debug('INSERT %s%s' % (table, post_data))
		return handle_api_exceptions(url, self.session.post, headers=headers, data=json.dumps(post_data), _cursor=self)

	def execute_update(self, query):
		table = query.model._meta.db_table
		# this will break in multi-row updates
		if DJANGO_17_PLUS:
			pk = query.where.children[0].rhs
		elif DJANGO_16_PLUS:
			pk = query.where.children[0][3]
		else:
			pk = query.where.children[0].children[0][-1]
		assert pk
		url = self.session.auth.instance_url + API_STUB + ('/sobjects/%s/%s' % (table, pk))
		headers = {'Content-Type': 'application/json'}
		post_data = extract_values(query)
		log.debug('UPDATE %s(%s)%s' % (table, pk, post_data))
		ret = handle_api_exceptions(url, self.session.patch, headers=headers, data=json.dumps(post_data), _cursor=self)
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
		url = self.session.auth.instance_url + API_STUB + ('/sobjects/%s/%s' % (table, pk))

		log.debug('DELETE %s(%s)' % (table, pk))
		return handle_api_exceptions(url, self.session.delete, _cursor=self)

	def query_results(self, results):
		while True:
			for rec in results['records']:
				if rec['attributes']['type'] == 'AggregateResult' and hasattr(self.query, 'aggregate_select'):
					assert len(rec) -1 == len(list(self.query.aggregate_select.items()))
					# The 'attributes' info is unexpected for Django within fields.
					rec = [rec[k] for k, _ in self.query.aggregate_select.items()]
				yield rec

			if results['done']:
				break

			# see about Retrieving the Remaining SOQL Query Results
			# http://www.salesforce.com/us/developer/docs/api_rest/Content/dome_query.htm#retrieve_remaining_results_title
			response = self.query_more(results['nextRecordsUrl'])
			results = response.json(parse_float=decimal.Decimal)

	def __iter__(self):
		return iter(self.results)

	def fetchone(self):
		"""
		Fetch a single result from a previously executed query.
		"""
		try:
			return next(self.results)
		except StopIteration:
			return None

	def fetchmany(self, size=None):
		"""
		Fetch multiple results from a previously executed query.
		"""
		if size is None:
			size = 200
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
	if not d.tzinfo:
		import time
		tz = pytz.timezone(settings.TIME_ZONE)
		d = tz.localize(d, is_dst=time.daylight)
	# Format of `%z` is "+HHMM"
	tzname = datetime.datetime.strftime(d, "%z")
	return datetime.datetime.strftime(d, "%Y-%m-%dT%H:%M:%S.000") + tzname

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
