# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
TODO: command-line SOQL interface.
"""
from salesforce import DJANGO_18_PLUS

from django.core.exceptions import ImproperlyConfigured
if DJANGO_18_PLUS:
    from django.db.backends.base.client import BaseDatabaseClient
else:
    from django.db.backends import BaseDatabaseClient

def complain(*args, **kwargs):
    raise ImproperlyConfigured("DatabaseClient: Not yet implemented for the Salesforce backend.")

class DatabaseClient(BaseDatabaseClient):
    runshell = complain
