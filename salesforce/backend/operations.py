# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

import re

from django.db.backends import BaseDatabaseOperations

class DatabaseOperations(BaseDatabaseOperations):
	compiler_module = "salesforce.backend.compiler"
	
	def __init__(self, connection):
		super(DatabaseOperations, self).__init__()
		self.connection = connection

	def quote_name(self, name):
		return name
	
	def check_aggregate_support(self, aggregate_func):
		"""Check that the backend supports the provided aggregate

		This is used on specific backends to rule out known aggregates
		that are known to have faulty implementations. If the named
		aggregate function has a known problem, the backend should
		raise NotImplemented.
		"""
		pass

