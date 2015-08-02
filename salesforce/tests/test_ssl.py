"""no hacks -> we can import immediately

I expect that more services wil disable TLS 1.0 before SFDC and the maintainers of `requests` will fix the issue
without need to monkey patch long parts of requests code or to repeat hacks like the one criticised in .... issue.
"""
from django.conf import settings
from django.test import TestCase
from salesforce.backend.adapter import SslHttpAdapter
from .utils import skip, skipUnless
import requests
import ssl
import sys

# some tests will be run only if they are selected explicitely on the command
# line "test salesforce.tests.test_ssl.SSLTest..."
explicitely_selected = 'SslTest' in str(sys.argv)

class SslTest(TestCase):
	"""
	The valid results of these tests expect that your "wires" are not under
	attack at the time you are running tests.
	"""

	@staticmethod
	def verify_rejected_ssl(url):
		"""
		The utility verifies that the url raises SSLError if the remote server
		supports only weak ciphers.
		"""
		session = requests.Session()
		session.mount('https://', SslHttpAdapter())
		try:
			response = session.get(url)
			return False
		except requests.exceptions.SSLError as e:
			return True

	def test_to_server_without_tls_10(self):
		"""
		Verify that connection is possible to SFDC servers that disabled TLS 1.0
		"""
		session = requests.Session()
		session.mount('https://', SslHttpAdapter())
		try:
			response = session.get('https://tls1test.salesforce.com')
			exc = None
		except requests.exceptions.SSLError as e:
			exc = e
		if exc:
			raise type(exc)(exc.args[0], "Can not connect to server with disabled TLS 1.0")
		self.assertIn('TLS 1.0 Deactivation Test Passed', response.text)

	def test_under_downgrade_attack_to_ssl_3(self):
		"""
		Verify that the connection is rejected if the remote server (or man
		in the middle) claims that SSLv3 is the best supported protocol.
		"""
		# https://zmap.io/sslv3/sslv3test.html
		url = "https://ssl3.zmap.io/sslv3test.js"
		if not self.verify_rejected_ssl(url):
			raise Exception("The protocol SSLv3 should be disabled. see README")
		if SslHttpAdapter().sf_ssl_version == ssl.PROTOCOL_TLSv1:
			adapter = SslHttpAdapter(ssl_version=ssl.PROTOCOL_SSLv23)
			session = requests.Session()
			session.mount('https://', adapter)
			try:
				response = session.get(url)
				print("It is important to UPGRADE Python and/or SSL before you "
					"can enable automatic selection of the highest protocol, "
					"but you must catch both before February 2016. see README")
			except requests.exceptions.SSLError as e:
				print("Test passed that you can update settings now to "
					"\"import ssl; SF_SSL = {'ssl_version': ssl.PROTOCOL_SSLv23}\" "
					"in order to use new TLS protocols. see README") 

	# all ssllabs tests are from https://www.ssllabs.com/ssltest/viewMyClient.html
	@skipUnless(explicitely_selected, "these tests can be enabled on command line")
	def test_protocols_by_ssl_labs(self):
		session = requests.Session()
		session.mount('https://', SslHttpAdapter())
		response = session.get('https://www.ssllabs.com/ssltest/viewMyClient.html')
		self.assertIn("Your user agent has good protocol support", response.text)

	@skipUnless(explicitely_selected, "these tests can be enabled on command line")
	def test_vulnerability_logjam_by_ssl_labs(self):
		if not self.verify_rejected_ssl('https://www.ssllabs.com:10445/'):
			raise Exception("vulnerable to Logjam Attack")
		# reported first on May 20, 2015 and usually not fixed yet

	@skipUnless(explicitely_selected, "these tests can be enabled on command line")
	def test_vulnerability_freak_by_ssl_labs(self):
		if not self.verify_rejected_ssl('https://www.ssllabs.com:10444/'):
			raise Exception("vulnerable to FREAK Attack")

	@skipUnless(explicitely_selected, "these tests can be enabled on command line")
	def test_vulnerability_osx_by_ssl_labs(self):
		if not self.verify_rejected_ssl('https://www.ssllabs.com:10443/'):
			raise Exception("iOS and OS X TLS Authentication Vulnerability")
