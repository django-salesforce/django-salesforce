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
import re

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.backends import BaseDatabaseIntrospection
from django.utils.datastructures import SortedDict
from django.utils.encoding import force_text

from salesforce.backend import compiler, query
from salesforce import models

try:
	import json
except ImportError:
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
		'id'                            : 'AutoField',
		'masterrecord'                  : 'CharField',
		# multipicklist can be implemented by a descendant with a special validator + widget
		'multipicklist'                 : 'CharField',
		'percent'                       : 'DecimalField',
		'phone'                         : 'CharField',
		# picklist is ('CharField', {'choices': (...)})
		'picklist'                      : 'CharField',
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
			
			log.debug('Request API URL: %s' % url)
			response = query.handle_api_exceptions(url, self.connection.sf_session.get)
			# charset is detected from headers by requests package
			self._table_list_cache = response.json()
		return self._table_list_cache
	
	def table_description_cache(self, table):
		if(table not in self._table_description_cache):
			url = self.oauth['instance_url'] + query.API_STUB + ('/sobjects/%s/describe/' % table)
		
			log.debug('Request API URL: %s' % url)
			response = query.handle_api_exceptions(url, self.connection.sf_session.get)
			self._table_description_cache[table] = response.json()
			assert self._table_description_cache[table]['fields'][0]['type'] == 'id'
			assert self._table_description_cache[table]['fields'][0]['name'] == 'Id'
			del self._table_description_cache[table]['fields'][0]
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
			if not field['updateable'] or not field['createable']:
				# Fields that are result of a formula or system fields modified by triggers or by other apex code
				sf_read_only = (0 if field['updateable'] else 1) | (0 if field['createable'] else 2)
				# use symbolic names NOT_UPDATEABLE, NON_CREATABLE, READ_ONLY instead of 1, 2, 3
				params['sf_read_only'] = reverse_models_names[sf_read_only]
			if field['defaultValue'] is not None:
				params['default'] = field['defaultValue']
			if field['inlineHelpText']:
				params['help_text'] = field['inlineHelpText']
			if field['picklistValues']:
				params['choices'] = [(x['value'], x['label']) for x in field['picklistValues'] if x['active']]
			if field['referenceTo']:
				if field['relationshipName'] and field['name'].lower() == field['relationshipName'].lower() + 'id':
					# change '*id' to '*_id', e.g. the name 'Account' instead of 'AccountId'
					field['name'] = field['name'][:-2] + '_' + field['name'][-2:]
			# We prefer length over byteLength for internal_size.
			#(usually length == 3 * length for strings)
			result.append((
				field['name'], # name,
				field['type'], # type_code,
				field['length'], # display_size,
				field['length'], # internal_size,
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
		global last_introspected_model, last_with_important_related_name, last_read_only
		table2model = lambda table_name: table_name.title().replace('_', '').replace(' ', '').replace('-', '')
		result = {}
		reverse = {}
		last_with_important_related_name = []
		last_read_only = {}
		INDEX_OF_PRIMARY_KEY = 0
		for i, field in enumerate(self.table_description_cache(table_name)['fields']):
			if field['type'] == 'reference':
				result[i] = (INDEX_OF_PRIMARY_KEY, field['referenceTo'][0])
				reverse.setdefault(field['referenceTo'][0], []).append(field['name'])
				if not field['updateable'] or not field['createable']:
					sf_read_only = (0 if field['updateable'] else 1) | (0 if field['createable'] else 2)
					# use symbolic names NOT_UPDATEABLE, NON_CREATABLE, READ_ONLY instead of 1, 2, 3
					last_read_only[field['name']] = reverse_models_names[sf_read_only]
		for ref, ilist in reverse.items():
			similar_back_references = [x['name'] for x in self.table_description_cache(ref)['fields']
				if re.sub('Id$', '', x['name']).lower() == table2model(table_name).lower()]
			if len(ilist) >1 or similar_back_references:  # add `related_name` only if necessary
				last_with_important_related_name.extend(ilist)
		last_introspected_model = table2model(table_name)
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

	def get_additional_meta(self, table_name):
		item = [x for x in self.table_list_cache['sobjects'] if x['name'] == table_name][0]
		return ["verbose_name = '%s'" % item['label'],
			"verbose_name_plural = '%s'" % item['labelPlural'],
			"# keyPrefix = '%s'" % item['keyPrefix'],

		]


class SymbolicModelsName(object):
	"""A symbolic name from the `models` module.
	>>> assert models.READ_ONLY == 3
	>>> SymbolicName('READ_ONLY').value
	3
	>>> [SymbolicName('READ_ONLY')]
	[models.READ_ONLY]
	"""
	def __init__(self, name):
		self.name = 'models.%s' % name
		self.value = int(getattr(models, name))
	def __repr__(self):
		return self.name
	def __int__(self):
		return self.value


reverse_models_names = dict((obj.value, obj) for obj in
	[SymbolicModelsName(name) for name in ('NOT_UPDATEABLE', 'NOT_CREATEABLE', 'READ_ONLY')]
)
