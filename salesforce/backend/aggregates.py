# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

from django.db.models.sql.aggregates import *

class Count(Aggregate):
	is_ordinal = True
	sql_function = 'COUNT'
	sql_template = '%(function)s(%(distinct)s%(field)s)'

	def __init__(self, col, distinct=False, **extra):
		if(col == '*'):
			col = ''
		super(Count, self).__init__(col, distinct=distinct and 'DISTINCT ' or '', **extra)

