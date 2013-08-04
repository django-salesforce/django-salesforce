# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

import datetime
import pytz

from django.conf import settings
from django.test import TestCase

from salesforce.testrunner.example.models import Account, Contact, Lead, ChargentOrder
import django
import salesforce

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
	
	def test_update_date_auto(self):
		"""
		Test updating a date.
		"""
		
		account = Account.objects.all()[0]
		account.save()
		now = datetime.datetime.utcnow()
		last_timestamp = salesforce.backend.query.sf_last_timestamp
		if django.VERSION[:2] >= (1,4):
			now = now.replace(tzinfo=pytz.utc)
		else:
			last_timestamp = last_timestamp.replace(tzinfo=None)
		saved = Account.objects.get(pk=account.pk)
		self.assertGreaterEqual(saved.LastModifiedDate, now)
		self.assertLess(saved.LastModifiedDate, now + datetime.timedelta(seconds=5))
		self.assertEqual(saved.LastModifiedDate, last_timestamp)
	
	def test_insert_date(self):
		"""
		Test inserting a date.
		"""
		self.skipTest("TODO Fix this test for yourself please if you have such customize Account.")
		
		now = datetime.datetime.now()
		account = Account(
			FirstName = 'Joe',
			LastName = 'Freelancer',
			IsPersonAccount = False,
			LastLogin = now,
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
		lead = Lead.objects.get(Email__isnull=False, FirstName='User')
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
		from salesforce.testrunner.example.models import TimbaSurveysQuestion
		orders = TimbaSurveysQuestion.objects.all()[0:5]
		self.assertEqual(len(orders), 5)

	def test_update_date_custom(self):
		"""
		Test updating a timestamp in a normal field.
		"""
		# create
		contact = Contact(LastName='test_sf')
		contact.save()
		contact = Contact.objects.filter(Name='test_sf')[0]
		# update
		contact.EmailBouncedDate = now = datetime.datetime.now().replace(tzinfo=pytz.utc)
		contact.save()
		contact = Contact.objects.get(Id=contact.Id)
		# test
		self.assertEqual(contact.EmailBouncedDate.utctimetuple(), now.utctimetuple())
		# delete, including the old failed similar
		for x in Contact.objects.filter(Name='test_sf'):
			x.delete()
