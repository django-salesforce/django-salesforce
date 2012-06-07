# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

"""
Salesforce database backend for Django.
"""

import logging, urlparse

from django.core.exceptions import ImproperlyConfigured
from django.db.backends import BaseDatabaseFeatures, BaseDatabaseWrapper

from django.db.backends.postgresql_psycopg2.base import PostgresqlDatabaseOperations

from salesforce.backend.client import DatabaseClient
from salesforce.backend.creation import DatabaseCreation
from salesforce.backend.introspection import DatabaseIntrospection
from salesforce.backend.validation import DatabaseValidation
from salesforce.backend.operations import DatabaseOperations

log = logging.getLogger(__name__)

class DatabaseError(Exception):
	pass

class SalesforceError(DatabaseError):
	pass

class IntegrityError(DatabaseError):
	pass

class DatabaseFeatures(BaseDatabaseFeatures):
	"""
	Features this database provides.
	"""
	allows_group_by_pk = True
	supports_unspecified_pk = False

class DatabaseWrapper(BaseDatabaseWrapper):
	"""
	Core class that provides all DB support.
	"""
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
		'isnull': '!= %s',
	}

	def __init__(self, settings_dict, alias='default'):
		super(DatabaseWrapper, self).__init__(settings_dict, alias)
		
		self.validate_settings(settings_dict)
		
		self.features = DatabaseFeatures(self)
		self.ops = DatabaseOperations(self)
		self.client = DatabaseClient(self)
		self.creation = DatabaseCreation(self)
		self.introspection = DatabaseIntrospection(self)
		self.validation = DatabaseValidation(self)
	
	def validate_settings(self, d):
		for k in ('ENGINE', 'CONSUMER_KEY', 'CONSUMER_SECRET', 'USER', 'PASSWORD', 'HOST'):
			if(k not in d):
				raise ImproperlyConfigured("Required '%s' key missing from '%s' database settings." % (k, self.alias))
			elif not(d[k]):
				raise ImproperlyConfigured("'%s' key is the empty string in '%s' database settings." % (k, self.alias))
		
		try:
			urlparse.urlparse(d['HOST'])
		except Exception, e:
			raise ImproperlyConfigured("'HOST' key in '%s' database settings should be a valid URL: %s" % (self.alias, e))
	
	def cursor(self, query=None):
		"""
		Return a fake cursor for accessing the Salesforce API with SOQL.
		"""
		from salesforce.backend.query import CursorWrapper
		cursor = CursorWrapper(self, query)
		return cursor
	
	def quote_name(self, name):
		"""
		Do not quote column and table names in the SOQL dialect.
		"""
		return name
