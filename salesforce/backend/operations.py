# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

import re

import django.db.backends.utils

from salesforce import DJANGO_18_PLUS
from salesforce.models import DefaultedOnCreate

if DJANGO_18_PLUS:
	from django.db.backends.base.operations import BaseDatabaseOperations
else:
	from django.db.backends import BaseDatabaseOperations

"""
Default database operations, with unquoted names.
"""

class DatabaseOperations(BaseDatabaseOperations):
	compiler_module = "salesforce.backend.compiler"
	
	def connection_init(self):
		pass
	
	def sql_flush(self, style, tables, sequences):
		return []
	
	def quote_name(self, name):
		return name
	
	def value_to_db_datetime(self, value):
		"""
		We let the JSON serializer handle dates for us.
		"""
		return value

	def value_to_db_date(self, value):
		"""
		We let the JSON serializer handle dates for us.
		"""
		return value
	
	def value_to_db_decimal(self, value, *args):
		if str(value) == 'DEFAULTED_ON_CREATE':
			return value
		return super(DatabaseOperations, self).value_to_db_decimal(value, *args)

	def last_insert_id(self, cursor, db_table, db_column):
		return cursor.lastrowid

	def adapt_datefield_value(self, value):
		return value

	def adapt_datetimefield_value(self, value):
		return value

	def adapt_timefield_value(self, value):
		return value

	def adapt_decimalfield_value(self, value, max_digits, decimal_places):
		if isinstance(value, DefaultedOnCreate):
			return value
		return django.db.backends.utils.format_number(value, max_digits, decimal_places)
