# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

"""
Salesforce database backend for Django.
"""

import logging

from django.core.exceptions import ImproperlyConfigured
from django.db.backends import BaseDatabaseWrapper, BaseDatabaseClient, BaseDatabaseIntrospection, BaseDatabaseFeatures, BaseDatabaseValidation
from django.db.backends.creation import BaseDatabaseCreation
from django.db.models.sql import compiler

from django.db.backends.postgresql_psycopg2.base import PostgresqlDatabaseOperations
from django.db.backends.postgresql_psycopg2.base import PostgresqlDatabaseOperations

log = logging.getLogger(__name__)

def complain(*args, **kwargs):
	raise ImproperlyConfigured("Not yet implemented for the Salesforce backend.")

class SQLCompiler(compiler.SQLCompiler):
	def get_columns(self, with_aliases=False):
		cols = compiler.SQLCompiler.get_columns(self, with_aliases)
		return [x.split('.')[1].strip('"') for x in cols]
	
	def get_from_clause(self):
		result = []
		first = True
		for alias in self.query.tables:
			if not self.query.alias_refcount[alias]:
				continue
			try:
				name, alias, join_type, lhs, lhs_col, col, nullable = self.query.alias_map[alias]
			except KeyError:
				# Extra tables can end up in self.tables, but not in the
				# alias_map if they aren't in a join. That's OK. We skip them.
				continue
			#TODO: change this so the right stuff just ends up in alias_map
			if(name.startswith('salesforce_')):
				name = name[11:]
				name = ''.join([x.capitalize() for x in name.split('_')])
			connector = not first and ', ' or ''
			result.append('%s%s' % (connector, name))
			first = False
		return result, []

class DatabaseError(Exception):
	pass

class IntegrityError(DatabaseError):
	pass

#TODO: remove psycopg2 dependency
class DatabaseOperations(PostgresqlDatabaseOperations):
	pass

class DatabaseFeatures(BaseDatabaseFeatures):
	empty_fetchmany_value = ()
	update_can_self_select = False
	allows_group_by_pk = True
	related_fields_match_type = True
	allow_sliced_subqueries = False
	supports_forward_references = False
	supports_long_model_names = False
	supports_microsecond_precision = False
	supports_regex_backreferencing = False
	supports_date_lookup_using_string = False
	supports_timezones = False
	requires_explicit_null_ordering_when_grouping = True
	allows_primary_key_0 = False

class DatabaseCreation(BaseDatabaseCreation):
	pass

class DatabaseValidation(BaseDatabaseValidation):
	pass

class DatabaseClient(BaseDatabaseClient):
	runshell = complain

class DatabaseIntrospection(BaseDatabaseIntrospection):
	get_table_list = complain
	get_table_description = complain
	get_relations = complain
	get_indexes = complain

class DatabaseWrapper(BaseDatabaseWrapper):
	vendor = 'salesforce'
	operators = {
		'exact': '= %s',
		'iexact': 'LIKE %s',
		'contains': 'LIKE BINARY %s',
		'icontains': 'LIKE %s',
		'regex': 'REGEXP BINARY %s',
		'iregex': 'REGEXP %s',
		'gt': '> %s',
		'gte': '>= %s',
		'lt': '< %s',
		'lte': '<= %s',
		'startswith': 'LIKE BINARY %s',
		'endswith': 'LIKE BINARY %s',
		'istartswith': 'LIKE %s',
		'iendswith': 'LIKE %s',
	}

	def __init__(self, *args, **kwargs):
		super(DatabaseWrapper, self).__init__(dict())

		self.features = DatabaseFeatures(self)
		self.ops = DatabaseOperations(self)
		self.client = DatabaseClient(self)
		self.creation = DatabaseCreation(self)
		self.introspection = DatabaseIntrospection(self)
		self.validation = DatabaseValidation(self)
	
	def quote_name(self, name):
		return name

