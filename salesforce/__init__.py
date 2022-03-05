# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
A database backend for the Django ORM.

Allows access to all Salesforce objects accessible via the SOQL API.
"""
import logging

# Default version of Force.com API.
# It can be customized by settings.DATABASES['salesforce']['API_VERSION']
API_VERSION = '55.0'  # Summer '22

from salesforce.dbapi.exceptions import (  # NOQA pylint:disable=unused-import,useless-import-alias,wrong-import-position
    IntegrityError as IntegrityError, DatabaseError as DatabaseError, SalesforceError as SalesforceError,
)

__version__ = "4.1"

log = logging.getLogger(__name__)
