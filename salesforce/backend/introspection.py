# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

"""
Salesforce introspection code.
"""

import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.backends import BaseDatabaseIntrospection
from django.utils.encoding import force_unicode

from salesforce.backend import compiler, query

import restkit
try:
	import json
except ImportError, e:
	import simplejson as json

log = logging.getLogger(__name__)

class DatabaseIntrospection(BaseDatabaseIntrospection):
	data_types_reverse = {
		'base64'                        : 'TextField',
		'boolean'                       : 'BooleanField',
		'byte'                          : 'SmallIntegerField',
		'date'                          : 'DateField',
		'datetime'                      : 'DateTimeField',
		'double'                        : 'DecimalField',
		'int'                           : 'IntegerField',
		'string'                        : 'CharField',
		'time'                          : 'TimeField',
		'anyType'                       : 'CharField',
		'calculated'                    : 'CharField',
		'combobox'                      : 'CharField',
		'currency'                      : 'CharField',
		'datacategorygroupreference'    : 'CharField',
		'email'                         : 'CharField',
		'encryptedstring'               : 'CharField',
		'id'                            : 'CharField',
		'masterrecord'                  : 'CharField',
		'multipicklist'                 : 'CharField',
		'percent'                       : 'DecimalField',
		'phone'                         : 'CharField',
		'picklist'                      : 'CharField',
		'reference'                     : 'CharField',
		'combobox'                      : 'CharField',
		'textarea'                      : 'TextField',
		'url'                           : 'CharField',
	}
	
	def __init__(self, conn):
		BaseDatabaseIntrospection.__init__(self, conn)
		from salesforce import auth
		self.oauth = auth.authenticate(conn.settings_dict)
		self._table_list_cache = None
		self._table_description_cache = {}
	
	@property
	def table_list_cache(self):
		if(self._table_list_cache is None):
			url = self.oauth['instance_url'] + query.API_STUB + '/sobjects/'
			
			headers = dict()
			headers['Authorization'] = 'OAuth %s' % self.oauth['access_token']
			headers['Content-Type'] = 'application/json'
			
			resource = restkit.Resource(url)
			log.debug('Request API URL: %s' % url)
			response = query.handle_api_exceptions(url, resource.get, headers=headers)
			body = response.body_string()
			jsrc = force_unicode(body).encode(settings.DEFAULT_CHARSET)
			self._table_list_cache = json.loads(jsrc)
		return self._table_list_cache
	
	def table_description_cache(self, table):
		if(table not in self._table_description_cache):
			url = self.oauth['instance_url'] + query.API_STUB + ('/sobjects/%s/describe/' % table)
		
			headers = dict()
			headers['Authorization'] = 'OAuth %s' % self.oauth['access_token']
			headers['Content-Type'] = 'application/json'
		
			resource = restkit.Resource(url)
			log.debug('Request API URL: %s' % url)
			response = query.handle_api_exceptions(url, resource.get, headers=headers)
			body = response.body_string()
			jsrc = force_unicode(body).encode(settings.DEFAULT_CHARSET)
			self._table_description_cache[table] = json.loads(jsrc)
		return self._table_description_cache[table]
	
	def get_table_list(self, cursor):
		"Returns a list of table names in the current database."
		result = [x['name'] for x in self.table_list_cache['sobjects']]
		return result
	
	def get_table_description(self, cursor, table_name):
		"Returns a description of the table, with the DB-API cursor.description interface."
		result = []
		for field in self.table_description_cache(table_name)['fields']:
			result.append((
				field['name'], # name,
				field['type'], # type_code,
				field['length'], # display_size,
				field['byteLength'], # internal_size,
				field['precision'], # precision,
				field['scale'], # scale,
				field['nillable'], # null_ok,
			))
		return result
	
	def get_relations(self, cursor, table_name):
		"""
		Returns a dictionary of {field_index: (field_index_other_table, other_table)}
		representing all relationships to the given table. Indexes are 0-based.
		"""
		return dict()
	
	def get_indexes(self, cursor, table_name):
		"""
		Returns a dictionary of fieldname -> infodict for the given table,
		where each infodict is in the format:
			{'primary_key': boolean representing whether it's the primary key,
			 'unique': boolean representing whether it's a unique index}
		"""
		result = {}
		for field in self.table_description_cache(table_name)['fields']:
			result[field['name']] = dict(primary_key=(field['type'] == 'id'), unique=field['unique'])
		return result
