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

import socket
from django.conf import settings
import logging
log = logging.getLogger(__name__)

# The maximal number of retries for requests to SF API.
MAX_RETRIES = getattr(settings, 'REQUESTS_MAX_RETRIES', 1)


def getaddrinfo_wrapper(host, port, family=socket.AF_INET, socktype=0, proto=0, flags=0):
	"""Patched 'getaddrinfo' with default family IPv4 (enabled by settings IPV4_ONLY=True)"""
	return orig_getaddrinfo(host, port, family, socktype, proto, flags)

# patch to IPv4 if required and not patched by anything other yet
if getattr(settings, 'IPV4_ONLY', False) and socket.getaddrinfo.__module__ in ('socket', '_socket'):
	log.info("Patched socket to IPv4 only")
	orig_getaddrinfo = socket.getaddrinfo
	# replace the original socket.getaddrinfo by our version
	socket.getaddrinfo = getaddrinfo_wrapper
