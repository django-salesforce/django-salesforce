# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

import datetime

from django.test import TestCase

from salesforce.testrunner.example.models import Account, Lead, ChargentOrder

import logging
log = logging.getLogger(__name__)

test_email = 'test-djsf-unittests-email@example.com'

class BasicSOQLTest(TestCase):
	def setUp(self):
		"""
		Create our test lead record.
		"""
		self.test_lead = Lead(
			FirstName	= "User",
			LastName	= "Unittest General",
			Email		= test_email,
			Status		= 'Open',
		)
		self.test_lead.save()
	
	def tearDown(self):
		"""
		Clean up our test lead record.
		"""
		self.test_lead.delete()
	
	def test_select_all(self):
		"""
		Get the first five account records.
		"""
		accounts = Account.objects.all()[0:5]
		self.assertEqual(len(accounts), 5)
	
	def test_update_date(self):
		"""
		Test updating a date.
		"""
		self.skipTest("Need to find a suitable *standard* model field to test datetime updates.")
		
		account = Account.objects.all()[0]
		account.LastLogin = now = datetime.datetime.now()
		account.save()
		
		saved = Account.objects.get(pk=account.pk)
		self.assertEqual(account.LastLogin, now)
	
	def test_insert_date(self):
		"""
		Test inserting a date.
		"""
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
	
	def test_get(self):
		"""
		Get the test lead record.
		"""
		lead = Lead.objects.get(Email=test_email)
		self.assertEqual(lead.FirstName, 'User')
		self.assertEqual(lead.LastName, 'Unittest General')
	
	def test_insert(self):
		"""
		Create a lead record, and make sure it ends up with a valid Salesforce ID.
		"""
		test_lead = Lead(FirstName="User", LastName="Unittest Inserts", Email='test-djsf-inserts-email@example.com')
		test_lead.save()
		self.assertEqual(len(test_lead.pk), 18)
		test_lead.delete()
	
	def test_delete(self):
		"""
		Create a lead record, then delete it, and make sure it's gone.
		"""
		test_lead = Lead(FirstName="User", LastName="Unittest Deletes", Email='test-djsf-delete-email@example.com')
		test_lead.save()
		test_lead.delete()
		
		self.assertRaises(Lead.DoesNotExist, Lead.objects.get, Email='test-djsf-delete-email@example.com')
	
	def test_update(self):
		"""
		Update the test lead record, then delete it.
		"""
		test_lead = Lead.objects.get(Email=test_email)
		self.assertEquals(test_lead.FirstName, 'User')
		
		test_lead.FirstName = 'Tested'
		test_lead.save()
		
		fetched_lead = Lead.objects.get(Email=test_email)
		self.assertEqual(fetched_lead.FirstName, 'Tested')

	def test_custom_objects(self):
		"""
		Make sure custom objects work.
		"""
		orders = ChargentOrder.objects.all()[0:5]
		self.assertEqual(len(orders), 5)

