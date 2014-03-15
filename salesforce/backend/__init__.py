# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Database backend for the Salesforce API.
"""

from django.conf import settings

sf_alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
