# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

from django.core.exceptions import ImproperlyConfigured
from django.db.backends import BaseDatabaseIntrospection

def complain(*args, **kwargs):
	raise ImproperlyConfigured("DatabaseIntrospection: Not yet implemented for the Salesforce backend.")

class DatabaseIntrospection(BaseDatabaseIntrospection):
	def get_field_type(self, data_type, description):
		"""
		Hook for a database backend to use the cursor description to
		match a Django field type to a database column.
		"""
		import pdb; pdb.set_trace()
	
