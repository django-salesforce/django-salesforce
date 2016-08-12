# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Aggregates like COUNT(), MAX(), MIN() are customized here.
"""
from salesforce import DJANGO_18_PLUS

if DJANGO_18_PLUS:
    from django.db.models.aggregates import *  # NOQA
    from django.db.models.aggregates import Aggregate
else:
    from django.db.models.sql.aggregates import *  # NOQA


class Count(Aggregate):
    """
    A customized Count class that uses the COUNT() syntax instead of COUNT(*).
    """
    is_ordinal = True
    sql_function = 'COUNT'
    sql_template = '%(function)s(%(distinct)s%(field)s)'

    def __init__(self, col, distinct=False, **extra):
        if(col == '*'):
            col = ''
        super(Count, self).__init__(col, distinct=distinct and 'DISTINCT ' or '', **extra)
