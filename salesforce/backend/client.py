# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
(empty) Module for command-line dbshell  (like django.db.backends.*.client)
"""

from django.core.exceptions import ImproperlyConfigured
from django.db.backends.base.client import BaseDatabaseClient


def complain(*args, **kwargs):
    raise ImproperlyConfigured("DatabaseClient: Not yet implemented for the Salesforce backend.")


class DatabaseClient(BaseDatabaseClient):
    # pylint:disable=too-few-public-methods
    runshell = complain
