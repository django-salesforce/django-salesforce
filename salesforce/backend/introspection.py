# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce introspection code.
"""

import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.backends import BaseDatabaseIntrospection
from django.utils.datastructures import SortedDict
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
		'currency'                      : 'DecimalField',
		'datacategorygroupreference'    : 'CharField',
		'email'                         : 'EmailField',
		'encryptedstring'               : 'CharField',
		'id'                            : ('CharField', {'editable': False}), # ForeignKey or # TODO but RecordType is editable with a choices list
		'masterrecord'                  : 'CharField',
		'multipicklist'                 : 'CharField',  # TODO a descendant with a special validator + widget
		'percent'                       : 'DecimalField',
		'phone'                         : 'CharField',
		'picklist'                      : 'CharField',  # TODO {'choices': (...)}
		'reference'                     : 'ForeignKey',
		'textarea'                      : 'TextField',
		'url'                           : 'URLField',
	}
	
	def __init__(self, conn):
		BaseDatabaseIntrospection.__init__(self, conn)
		self._table_list_cache = None
		self._table_description_cache = {}
		self._oauth = None
	
	@property
	def oauth(self):
		from salesforce import auth
		return auth.authenticate(self.connection.settings_dict)
	
	@property
	def table_list_cache(self):
		if(self._table_list_cache is None):
			url = self.oauth['instance_url'] + query.API_STUB + '/sobjects/'
			
			headers = dict()
			headers['Authorization'] = 'OAuth %s' % self.oauth['access_token']
			headers['Content-Type'] = 'application/json'
			
			salesforce_timeout = getattr(settings, 'SALESFORCE_QUERY_TIMEOUT', 3)
			resource = restkit.Resource(url, timeout=salesforce_timeout)
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
		
			salesforce_timeout = getattr(settings, 'SALESFORCE_QUERY_TIMEOUT', 3)
			resource = restkit.Resource(url, timeout=salesforce_timeout)
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
			params = SortedDict()
			if field['label']:
				params['verbose_name'] = field['label']
			if not field['updateable']:
				params['sf_read_only'] = True
			if field['defaultValue'] is not None:
				params['default'] = field['defaultValue']
			if field['inlineHelpText']:
				params['help_text'] = field['inlineHelpText']
			if field['picklistValues']:
				params['choices'] = [(x['value'], x['label']) for x in field['picklistValues'] if x['active']]
			if field['referenceTo']:
				# e.g. the name 'Account' instead of 'AccountId'
				#if not field['name'] or not field['relationshipName']:
				if field['relationshipName'] and field['name'].lower() == field['relationshipName'].lower() + 'id':
					# change '*id' to '*_id' 
					field['name'] = field['name'][:-2] + '_' + field['name'][-2:]
				if 'requires_related_name' in field:
					import pdb; pdb.set_trace()
					params['related_name'] = ('%s_%s_set' % (table_name.replace('_', ''), field['name'].replace('_', ''))).lower()
			if '*2013' in field['name']:
			    import pdb; pdb.set_trace()
			result.append((
				field['name'], # name,
				field['type'], # type_code,
				field['length'], # display_size,
				field['byteLength'], # internal_size,
				field['precision'], # precision,
				field['scale'], # scale,
				field['nillable'], # null_ok,
				params,
			))
		return result
	
	def get_relations(self, cursor, table_name):
		"""
		Returns a dictionary of {field_index: (field_index_other_table, other_table)}
		representing all relationships to the given table. Indexes are 0-based.
		"""
		table2model = lambda table_name: table_name.title().replace('_', '').replace(' ', '').replace('-', '')
		result = {}
		reverse = {}
		INDEX_OF_PRIMARY_KEY = 0
		for i, field in enumerate(self.table_description_cache(table_name)['fields']):
			if field['type'] == 'reference':
				result[i] = (INDEX_OF_PRIMARY_KEY, field['referenceTo'][0])
				reverse.setdefault(field['referenceTo'][0], []).append(i)
		for ref, ilist in reverse.items():
		    if len(ilist) >1:
			for i in ilist:
			    self.table_description_cache(table_name)['fields'][i]['requires_related_name'] = True
		return result
	
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
