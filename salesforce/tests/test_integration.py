# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

import datetime

from django.conf import settings
from django.test import TestCase

from salesforce.testrunner.example.models import Account, Lead, ChargentOrder, TimbaSurveysQuestion, Email

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
			Company = "Some company, Ltd.",
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
	
	def test_select_all(self):
		"""
		Get the first five account records.
		"""
		accounts = Account.objects.all()[0:5]
		self.assertEqual(len(accounts), 5)
	
	def test_foreign_key(self):
		account = Account.objects.all()[0]
		user = account.Owner
		self.assertEqual(user.Email, settings.DATABASES['salesforce']['USER'].rsplit('.', 1)[0])  # 'admins@freelancersunion.org.prod001'
	
	def test_update_date_custom(self):
		"""
		Test updating a date in custom field.
		"""
		# TODO Read-only fields like automatically updated DateCreated, DateModified
		# can not be used in models, otherwise nothing in that model can be saved
		
		email = Email.objects.get(Contact='003c000000Lja0J')
		email.LastUsedDate = now = datetime.datetime.now()
		email.save()
		
		saved = Email.objects.get(pk=email.pk)
		self.assertEqual(email.LastUsedDate, now)
	
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
			#FirstName = 'Joe',
			#LastName = 'Freelancer',
			LastLogin = now,
			#IsPersonAccount = False,
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
	
	def test_not_null(self):
		"""
		Get the test lead record.
		"""
		lead = Lead.objects.get(Email__isnull=False)
		self.assertEqual(lead.FirstName, 'User')
		self.assertEqual(lead.LastName, 'Unittest General')
	
	def test_unicode(self):
		"""
		Make sure weird unicode breaks properly.
		"""
		test_lead = Lead(FirstName=u'\u2603', LastName="Unittest Unicode", Email='test-djsf-unicode-email@example.com', Company="Some company")
		test_lead.save()
		self.assertEqual(test_lead.FirstName, u'\u2603')
		test_lead.delete()
	
	def test_date_comparison(self):
		"""
		Test that date comparisons work properly.
		"""
		yesterday = datetime.datetime(2011,06,26)
		accounts = Account.objects.filter(LastModifiedDate__gt=yesterday)
		self.assertEqual(bool(accounts.count()), True)
	
	def test_insert(self):
		"""
		Create a lead record, and make sure it ends up with a valid Salesforce ID.
		"""
		test_lead = Lead(FirstName="User", LastName="Unittest Inserts", Email='test-djsf-inserts-email@example.com', Company="Some company")
		test_lead.save()
		self.assertEqual(len(test_lead.pk), 18)
		test_lead.delete()
	
	def test_delete(self):
		"""
		Create a lead record, then delete it, and make sure it's gone.
		"""
		test_lead = Lead(FirstName="User", LastName="Unittest Deletes", Email='test-djsf-delete-email@example.com', Company="Some company")
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
		orders = TimbaSurveysQuestion.objects.all()[0:5]
		self.assertEqual(len(orders), 5)

