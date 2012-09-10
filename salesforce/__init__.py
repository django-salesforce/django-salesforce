# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

"""
A database backend for the Django ORM.

Allows access to all Salesforce objects accessible via the SOQL API.
"""

import httplib, ssl, urllib2, socket, logging

log = logging.getLogger(__name__)

# custom HTTPS opener, SalesForce test server supports SSLv3 only
class HTTPSConnectionV3(httplib.HTTPSConnection):
	def __init__(self, *args, **kwargs):
		httplib.HTTPSConnection.__init__(self, *args, **kwargs)
		
	def connect(self):
		sock = socket.create_connection((self.host, self.port), self.timeout)
		if self._tunnel_host:
			self.sock = sock
			self._tunnel()
		try:
			self.sock = ssl.wrap_socket(sock, self.key_file, self.cert_file, ssl_version=ssl.PROTOCOL_SSLv3)
		except ssl.SSLError, e:
			log.warning("SSL doesn't support PROTOCOL_SSLv3, trying PROTOCOL_SSLv23")
			self.sock = ssl.wrap_socket(sock, self.key_file, self.cert_file, ssl_version=ssl.PROTOCOL_SSLv23)
			
class HTTPSHandlerV3(urllib2.HTTPSHandler):
	def https_open(self, req):
		return self.do_open(HTTPSConnectionV3, req)

# install opener
urllib2.install_opener(urllib2.build_opener(HTTPSHandlerV3()))