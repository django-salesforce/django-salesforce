# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce database backend for Django.
"""

import logging, urlparse

from django.core.exceptions import ImproperlyConfigured
from django.db.backends import BaseDatabaseFeatures, BaseDatabaseWrapper

from salesforce.backend.client import DatabaseClient
from salesforce.backend.creation import DatabaseCreation
from salesforce.backend.introspection import DatabaseIntrospection
from salesforce.backend.validation import DatabaseValidation
from salesforce.backend.operations import DatabaseOperations
from salesforce.backend.driver import IntegrityError, DatabaseError
from salesforce.backend import driver as Database

log = logging.getLogger(__name__)

class SalesforceError(DatabaseError):
	pass

class DatabaseFeatures(BaseDatabaseFeatures):
	"""
	Features this database provides.
	"""
	allows_group_by_pk = True
	supports_unspecified_pk = False
	can_return_id_from_insert = False
	supports_select_related = False
	supports_transactions = False

class DatabaseWrapper(BaseDatabaseWrapper):
	"""
	Core class that provides all DB support.
	"""
	vendor = 'salesforce'
	# Operators [contains, startswithm, endswith] are incorrectly
	# case insensitive like sqlite3.
	operators = {
		'exact': '= %s',
		'iexact': 'LIKE %s',
		'contains': 'LIKE %s',
		'icontains': 'LIKE %s',
		#'regex': 'REGEXP %s',  # unsupported
		#'iregex': 'REGEXP %s',
		'gt': '> %s',
		'gte': '>= %s',
		'lt': '< %s',
		'lte': '<= %s',
		'startswith': 'LIKE %s',
		'endswith': 'LIKE %s',
		'istartswith': 'LIKE %s',
		'iendswith': 'LIKE %s',
		# TODO remove 'isnull' because it's incorrect and unused
		#'isnull': '!= %s',
	}

	Database = Database

	def __init__(self, settings_dict, alias='default'):
		super(DatabaseWrapper, self).__init__(settings_dict, alias)
		
		self.validate_settings(settings_dict)
		
		self.features = DatabaseFeatures(self)
		self.ops = DatabaseOperations(self)
		self.client = DatabaseClient(self)
		self.creation = DatabaseCreation(self)
		self.introspection = DatabaseIntrospection(self)
		self.validation = DatabaseValidation(self)
	
	def get_connection_params(self):
		settings_dict = self.settings_dict
		params = settings_dict.copy()
		params.update(settings_dict['OPTIONS'])
		return params

	def get_new_connection(self, conn_params):
		# only simulated a connection interface without connecting really
		return Database.connect(**conn_params)

	def init_connection_state(self):
		pass  # nothing to init

	def _set_autocommit(self, autocommit):
		# SF REST API uses autocommit, but until rollback it is not a
		# serious problem to ignore autocommit off
		pass

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
