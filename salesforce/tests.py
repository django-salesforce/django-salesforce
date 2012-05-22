# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

from django.test import TestCase

from salesforce.models import Account, Lead, ChargentOrder

import logging
log = logging.getLogger(__name__)

test_email = 'test-q078hv5osagadskfjhfg@example.com'

class BasicSOQLTest(TestCase):
	def setUp(self):
		self.test_lead = Lead(FirstName="Test", LastName="User", Email=test_email)
		self.test_lead.save()
	
	def tearDown(self):
		self.test_lead.delete()
	
	def test_select_all(self):
		"""
		Get the first five account records.
		"""
		accounts = Account.objects.all()[0:5]
		self.assertEqual(len(accounts), 5)
	
	def test_select_one(self):
		"""
		Get the test lead record.
		"""
		lead = Lead.objects.get(Email=test_email)
		self.assertEqual(lead.FirstName, 'Test')
		self.assertEqual(lead.LastName, 'User')
	
	def test_insert(self):
		"""
		Create a test lead record, and make sure it ends up with a valid Salesforce ID.
		"""
		test_lead = Lead(FirstName="Test2", LastName="User2", Email='test-3408f7hc5pu0823@example.com')
		test_lead.save()
		self.assertEqual(len(test_lead.pk), 18)
	
	def test_delete(self):
		"""
		Create a test lead record, then delete it.
		"""
		test_lead = Lead(FirstName="Test", LastName="User", Email='test-54wo89fg67aiwduyfg@example.com')
		test_lead.save()
		test_lead.delete()
		
		self.assertRaises(Lead.DoesNotExist, Lead.objects.get, Email='test-54wo89fg67aiwduyfg@example.com')
	
	def test_update(self):
		"""
		Create a test lead record, then delete it.
		"""
		test_lead = Lead.objects.get(Email=test_email)
		self.assertEquals(test_lead.FirstName, 'Test')
		
		test_lead.FirstName = 'Tested'
		test_lead.save()
		
		fetched_lead = Lead.objects.get(Email=test_email)
		self.assertEqual(fetched_lead.FirstName, 'Tested')

class ChargentTest(TestCase):
	def test_query_orders(self):
		orders = ChargentOrder.objects.all()[0:5]
		self.assertEqual(len(orders), 5)

