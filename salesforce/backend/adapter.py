"""requests adapter for more secure SSL"""
# Motivated by "Salesforce recommends customers disable SSL 3.0 encryption":
# https://help.salesforce.com/apex/HTViewSolution?urlname=Salesforce-disabling-SSL-3-0-encryption&language=en_US
# Solution copied from:
# http://docs.python-requests.org/en/latest/user/advanced/#example-specific-ssl-version

import ssl
from django.conf import settings
from requests.adapters import HTTPAdapter, DEFAULT_POOLBLOCK
from requests.packages.urllib3.poolmanager import PoolManager

class SslHttpAdapter(HTTPAdapter):
	"""
	Transport adapter with hardened SSL version.

	ssl_version: this parameter is inteded for tests to override the value
			`SF_SSL['ssl_version']`.
			Expected values are `ssl.PROTOCOL_TLSv1` or `ssl.PROTOCOL_SSLv23`.
	"""
	def __init__(self, *args, **kwargs):
		# TODO Change the default SSL version to ssl.PROTOCOL_SSLv23 in the
		#      autumn release v0.7.
		default_ssl_version = getattr(settings, 'SF_SSL', {}).get('ssl_version',
				ssl.PROTOCOL_TLSv1)
		self.sf_ssl_version = kwargs.pop('ssl_version', default_ssl_version)
		super(SslHttpAdapter, self).__init__(*args, **kwargs)

	def init_poolmanager(self, connections, maxsize, block=DEFAULT_POOLBLOCK):
		self._pool_connections = connections
		self._pool_maxsize = maxsize
		self._pool_block = block
		self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize,
									   block=block,
									   ssl_version=self.sf_ssl_version)
