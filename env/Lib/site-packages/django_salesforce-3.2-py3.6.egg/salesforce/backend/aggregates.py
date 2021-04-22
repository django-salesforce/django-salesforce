# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
OBSOLETED Aggregates like COUNT();  (like django.db.models.aggregates)

Obsoleted and unused, because it is the same for all backends. (but a nice inspiration)
prefer patch as_salesforce
"""
# from django.db.models.aggregates import Aggregate
#
#
# class Count(Aggregate):  # pylint: disable=function-redefined
#     """
#     A customized Count class that uses the COUNT() syntax instead of COUNT(*).
#     """
#     # pylint:disable=abstract-method  # undefined __and__, __or__, __rand__, __ror__
#     is_ordinal = True
#     sql_function = 'COUNT'
#     sql_template = '%(function)s(%(distinct)s%(field)s)'
#
#     def __init__(self, col, distinct=False, **extra):
#         if col == '*':
#             col = ''
#         super(Count, self).__init__(col, distinct='DISTINCT ' if distinct else '', **extra)
