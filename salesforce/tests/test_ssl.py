"""no hacks -> we can import immediately

I expect that more services wil disable TLS 1.0 before SFDC and the maintainers of `requests` will fix the issue
without need to monkey patch long parts of requests code or to repeat hacks like the one criticised in .... issue.
"""
from django.conf import settings
from django.test import TestCase
from salesforce.backend.adapter import SslHttpAdapter
from ..backend.test_helpers import skip, skipUnless
import requests
import ssl
import sys

# some tests will be run only if they are selected explicitely on the command
# line "test salesforce.tests.test_ssl.SSLTest..."
explicitely_selected = 'SslTest' in str(sys.argv)
skiptest_tls_11 = getattr(settings, 'SF_SSL', {}).get('skiptest_tls_11', False)

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

	@skipUnless(not skiptest_tls_11, "Skipped due to skiptest_tls_11")
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
			messages = ["Can not connect to server with disabled TLS 1.0"]
			response = None
			if SslHttpAdapter().sf_ssl_version != ssl.PROTOCOL_SSLv23:
				adapter = SslHttpAdapter(ssl_version=ssl.PROTOCOL_SSLv23)
				session = requests.Session()
				session.mount('https://', adapter)
				try:
					response = session.get('https://tls1test.salesforce.com')
				except requests.exceptions.SSLError as e:
					pass
			if response:
				messages.append("This can be fixed by setting "
					"\"import ssl; SF_SSL = {'ssl_version': ssl.PROTOCOL_SSLv23}\" ")
				if self.verify_rejected_ssl("https://ssl3.zmap.io/sslv3test.js"):
					messages.append("The setting should be fixed just now.")
				else:
					messages.append("but this would enable the insecure SSLv3 protocol")
			else:
				messages.append("The system should be updated to enable newer TLS protocols.")
			messages.append("see README")
			raise type(exc)(exc.args[0], '\n' + '\n'.join(messages))
		self.assertIn('TLS 1.0 Deactivation Test Passed', response.text)

	def test_under_downgrade_attack_to_ssl_3(self):
		"""
		Verify that the connection is rejected if the remote server (or man
		in the middle) claims that SSLv3 is the best supported protocol.
		"""
		# https://zmap.io/sslv3/sslv3test.html
		url = "https://ssl3.zmap.io/sslv3test.js"
		if not self.verify_rejected_ssl(url):
			raise Exception("The protocol SSLv3 should be disabled for better security "
					"if possible. (It is disabled on all new systems.) see README")

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
