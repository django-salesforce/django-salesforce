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

from salesforce.dbapi.exceptions import (  # NOQA pylint:disable=unused-import,useless-import-alias
    IntegrityError as IntegrityError, DatabaseError as DatabaseError, SalesforceError as SalesforceError,
)

__version__ = "0.9"

log = logging.getLogger(__name__)

# Default version of Force.com API.
# It can be set by setattr() to any lower or higher supported value.
# (The highest version can be set by "salesforce.utils.set_highest_api_version()".
# It is useful for development, a constant version is for production.)

# Example for settings.py:
# >>> import salesforce
# >>> setattr(salesforce, 'API_VERSION', '37.0')

API_VERSION = '46.0'  # Summer '19
# API_VERSION = '47.0'  # Winter '20
