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
from django.db.backends import BaseDatabaseFeatures, BaseDatabaseWrapper
from django.db.backends.signals import connection_created

from django.db.backends.postgresql_psycopg2.base import PostgresqlDatabaseOperations

from salesforce.backend.client import DatabaseClient
from salesforce.backend.creation import DatabaseCreation
from salesforce.backend.introspection import DatabaseIntrospection
from salesforce.backend.validation import DatabaseValidation

from salesforce import sfauth

log = logging.getLogger(__name__)

def complain(*args, **kwargs):
	raise ImproperlyConfigured("Not yet implemented for the Salesforce backend.")

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

	def __init__(self, settings_dict, alias='default'):
		super(DatabaseWrapper, self).__init__(settings_dict, alias)
		
		connection_created.send(sender=self.__class__, connection=self)
		
		self.features = DatabaseFeatures(self)
		self.ops = DatabaseOperations(self)
		self.client = DatabaseClient(self)
		self.creation = DatabaseCreation(self)
		self.introspection = DatabaseIntrospection(self)
		self.validation = DatabaseValidation(self)
	
	def _cursor(self):
		cursor = CursorWrapper(self.settings_dict)
		return cursor
	
	def quote_name(self, name):
		return name

class CursorWrapper(object):
	def __init__(self, settings_dict):
		self.settings_dict = settings_dict
		sfauth.authenticate(self.settings_dict)

