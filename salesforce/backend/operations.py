# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

import re

from django.db.backends import BaseDatabaseOperations

"""
Default database operations, with unquoted names.
"""

class DatabaseOperations(BaseDatabaseOperations):
	compiler_module = "salesforce.backend.compiler"
	
	def __init__(self, connection):
		super(DatabaseOperations, self).__init__()
		self.connection = connection

	def quote_name(self, name):
		return name
