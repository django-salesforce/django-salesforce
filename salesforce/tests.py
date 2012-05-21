# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

from django.test import TestCase

from salesforce.models import Account, Lead

import logging
log = logging.getLogger(__name__)

class AccountsTest(TestCase):
	def test_select_all(self):
		"""
		Get the first five account records.
		"""
		accounts = Account.objects.all()[0:5]
		self.assertEqual(len(accounts), 5)
	
	def test_select_one(self):
		"""
		Get phil's account record.
		"""
		account = Account.objects.get(PersonEmail='phil@bubblehouse.org')
		self.assertEqual(account.Name, 'Philip Christensen')
	
	def test_insert_and_delete_lead(self):
		"""
		Create a test account record, then delete it.
		"""
		test_email = 'test-5wl6ie4sdf645rtf67un@example.com'
		
		test_lead = Lead(FirstName="Test", LastName="User", Email=test_email)
		test_lead.save()
		
		fetched_account = Lead.objects.get(Email=test_email)
		fetched_account.delete()
