# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

from django.test import TestCase

from salesforce.models import Account

class AccountsTest(TestCase):
	def test_limited_query(self):
		"""
		Get the first five account records.
		"""
		accounts = Account.objects.all()[0:5]
		self.assertEqual(len(accounts), 5)
