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
import httplib2, ssl
from pkg_resources import parse_version

import django
DJANGO_14 = (parse_version(django.get_version()) >= parse_version('1.4'))
DJANGO_15 = django.VERSION[:2] >= (1, 5)
DJANGO_16 = django.VERSION[:2] >= (1, 6)

log = logging.getLogger(__name__)

def ssl_wrap_socket(sock, key_file, cert_file, disable_validation, ca_certs):
	if disable_validation:
		cert_reqs = ssl.CERT_NONE
	else:
		cert_reqs = ssl.CERT_REQUIRED
	try:
		sock = ssl.wrap_socket(sock, keyfile=key_file, certfile=cert_file,
                               cert_reqs=cert_reqs, ca_certs=ca_certs, ssl_version=ssl.PROTOCOL_SSLv3)
	except ssl.SSLError, e:
		log.warning("SSL doesn't support PROTOCOL_SSLv3, trying PROTOCOL_SSLv23")
		sock = ssl.wrap_socket(sock, keyfile=key_file, certfile=cert_file,
                               cert_reqs=cert_reqs, ca_certs=ca_certs, ssl_version=ssl.PROTOCOL_SSLv23)
	return sock

httplib2._ssl_wrap_socket = ssl_wrap_socket

