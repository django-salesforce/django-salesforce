# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Default validation code.
"""
from salesforce import DJANGO_18_PLUS

if DJANGO_18_PLUS:
    from django.db.backends.base.validation import BaseDatabaseValidation
else:
    from django.db.backends import BaseDatabaseValidation

class DatabaseValidation(BaseDatabaseValidation):
    pass

