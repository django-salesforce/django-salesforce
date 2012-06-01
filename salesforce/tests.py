# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

import datetime

from django.test import TestCase

from salesforce.models import Account, Lead, ChargentOrder

import logging
log = logging.getLogger(__name__)

test_email = 'test-djsf-unittests-email@example.com'

class BasicSOQLTest(TestCase):
	def setUp(self):
		self.test_lead = Lead(
			FirstName	= "User",
			LastName	= "Unittest General",
			Email		= test_email,
			Status		= 'Open',
		)
		self.test_lead.save()
	
	def tearDown(self):
		self.test_lead.delete()
	
	def test_select_all(self):
		"""
		Get the first five account records.
		"""
		accounts = Account.objects.all()[0:5]
		self.assertEqual(len(accounts), 5)
	
	def test_update_date(self):
		self.skipTest("Need to find a suitable *standard* model field to test datetime updates.")
		
		account = Account.objects.all()[0]
		account.LastLogin = now = datetime.datetime.now()
		account.save()
		
		saved = Account.objects.get(pk=account.pk)
		self.assertEqual(account.LastLogin, now)
	
	def test_insert_date(self):
		self.skipTest("Need to find a suitable *standard* model field to test datetime inserts.")
		
		now = datetime.datetime.now()
		account = Account(
			FirstName = 'Joe',
			LastName = 'Freelancer',
			LastLogin = now,
			IsPersonAccount = False,
		)
		account.save()
		
		saved = Account.objects.get(pk=account.pk)
		self.assertEqual(saved.LastLogin, now)
		self.assertEqual(saved.IsPersonAccount, False)
		
		saved.delete()
	
	def test_select_one(self):
		"""
		Get the test lead record.
		"""
		lead = Lead.objects.get(Email=test_email)
		self.assertEqual(lead.FirstName, 'User')
		self.assertEqual(lead.LastName, 'Unittest General')
	
	def test_insert(self):
		"""
		Create a test lead record, and make sure it ends up with a valid Salesforce ID.
		"""
		test_lead = Lead(FirstName="User", LastName="Unittest Inserts", Email='test-djsf-inserts-email@example.com')
		test_lead.save()
		self.assertEqual(len(test_lead.pk), 18)
		test_lead.delete()
	
	def test_delete(self):
		"""
		Create a test lead record, then delete it.
		"""
		test_lead = Lead(FirstName="User", LastName="Unittest Deletes", Email='test-djsf-delete-email@example.com')
		test_lead.save()
		test_lead.delete()
		
		self.assertRaises(Lead.DoesNotExist, Lead.objects.get, Email='test-djsf-delete-email@example.com')
	
	def test_update(self):
		"""
		Create a test lead record, then delete it.
		"""
		test_lead = Lead.objects.get(Email=test_email)
		self.assertEquals(test_lead.FirstName, 'User')
		
		test_lead.FirstName = 'Tested'
		test_lead.save()
		
		fetched_lead = Lead.objects.get(Email=test_email)
		self.assertEqual(fetched_lead.FirstName, 'Tested')

class ChargentTest(TestCase):
	def test_query_orders(self):
		orders = ChargentOrder.objects.all()[0:5]
		self.assertEqual(len(orders), 5)

