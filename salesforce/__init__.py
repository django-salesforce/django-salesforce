# django-salesforce
#
# by Hyneck Cernoch and Phil Christensen
# See LICENSE.md for details
#

"""
A database backend for the Django ORM.

Allows access to all Salesforce objects accessible via the SOQL API.
"""
import logging

# Default version of Force.com API.
# It can be customized by settings.DATABASES['salesforce']['API_VERSION']
API_VERSION = '65.0'  # Winter '26
# API_VERSION = '66.0'  # Spring '26  (enable after Feb 20, 2026)

from salesforce.dbapi.exceptions import (  # NOQA pylint:disable=unused-import,useless-import-alias,wrong-import-position
    IntegrityError as IntegrityError, DatabaseError as DatabaseError, SalesforceError as SalesforceError,
)

__version__ = "5.2"

log = logging.getLogger(__name__)
