# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Database backend for the Salesforce API.
"""

from __future__ import print_function
import socket
import sys
from django.conf import settings

sf_alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')

# The maximal number of retries for requests to SF API.
MAX_RETRIES = getattr(settings, 'REQUESTS_MAX_RETRIES', 1)


def getaddrinfo_wrapper(host, port, family=socket.AF_INET, socktype=0, proto=0, flags=0):
	    return orig_getaddrinfo(host, port, family, socktype, proto, flags)

# patch to IPv4 if required and not patched by anything other yet
if getattr(settings, 'IPV4_ONLY', False) and socket.getaddrinfo.__module__ in ('socket', '_socket'):
	print("Patched socket to IPv4 only", file=sys.stderr)
	orig_getaddrinfo = socket.getaddrinfo
	# replace the original socket.getaddrinfo by our version
	socket.getaddrinfo = getaddrinfo_wrapper
