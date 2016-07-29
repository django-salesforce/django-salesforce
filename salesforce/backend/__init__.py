# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Database backend for the Salesforce API.

No code in this directory is used with standard databases, even if a standard
database is used for running some application tests on objects defined by
SalesforceModel. All code for SF models that can be used with non SF databases
should be located directly in the 'salesforce' directory in files 'models.py',
'fields.py', 'manager.py', 'router.py', 'admin.py'.

All code here in salesforce.backend is private without public API. (It can be
changed anytime between versions.)

Incorrectly located files: (It is better not to change it now.)
    backend/manager.py   => manager.py
    auth.py              => backend/auth.py
"""

import logging
log = logging.getLogger(__name__)

# The maximal number of retries for timeouts in requests to Force.com API.
# Can be set dynamically
# None: use defaults from settings.REQUESTS_MAX_RETRIES (default 1)
# 0: no retry
# 1: one retry
MAX_RETRIES = None  # uses defaults below)


def get_max_retries():
    """Get the maximal number of requests retries"""
    global MAX_RETRIES
    from django.conf import settings
    if MAX_RETRIES is None:
        MAX_RETRIES = getattr(settings, 'REQUESTS_MAX_RETRIES', 1)
    return MAX_RETRIES
