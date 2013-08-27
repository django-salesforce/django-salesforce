# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

import datetime

from django.test import TestCase

from salesforce.testrunner.example.models import Contact, Lead, ChargentOrder

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
	
	def test_raw(self):
		"""
		Get the first five contact records.
		"""
		contacts = Contact.objects.raw("SELECT Id, LastName, FirstName FROM Contact")
		self.assertEqual(len(contacts), 2)
		'%s' % contacts[0].__dict__  # Check that all fields are accessible
	
	def test_raw_foreignkey_id(self):
		"""
		Get the first contact records by raw with a ForeignKey id field.
		"""
		contacts = Contact.objects.raw("SELECT Id, LastName, FirstName, OwnerId FROM Contact")
		self.assertEqual(len(contacts), 2)
		'%s' % contacts[0].__dict__  # Check that all fields are accessible
		self.assertContains(contacts[0].Owner.Email, '@')
	
	def test_select_all(self):
		"""
		Get the first five contact records.
		"""
		contacts = Contact.objects.all()[0:5]
		self.assertEqual(len(contacts), 2)
	
	def test_foreign_key(self):
		contact = Contact.objects.all()[0]
		user = contact.Owner
		self.assertEqual(user.Email, 'pchristensen@freelancersunion.org')
	
	def test_update_date(self):
		"""
		Test updating a date.
		"""
		self.skipTest("Need to find a suitable *standard* model field to test datetime updates.")
		
		contact = Contact.objects.all()[0]
		contact.LastLogin = now = datetime.datetime.now()
		contact.save()
		
		saved = Contact.objects.get(pk=contact.pk)
		self.assertEqual(contact.LastLogin, now)
	
	def test_insert_date(self):
		"""
		Test inserting a date.
		"""
		self.skipTest("Need to find a suitable *standard* model field to test datetime inserts.")
		
		now = datetime.datetime.now()
		contact = Contact(
			FirstName = 'Joe',
			LastName = 'Freelancer',
			LastLogin = now,
			IsPersonContact = False,
		)
		contact.save()
		
		saved = Contact.objects.get(pk=contact.pk)
		self.assertEqual(saved.LastLogin, now)
		self.assertEqual(saved.IsPersonContact, False)
		
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
		test_lead = Lead(FirstName=u'\u2603', LastName="Unittest Unicode", Email='test-djsf-unicode-email@example.com')
		test_lead.save()
		self.assertEqual(test_lead.FirstName, u'\u2603')
		test_lead.delete()
	
	def test_date_comparison(self):
		"""
		Test that date comparisons work properly.
		"""
		yesterday = datetime.datetime(2011,06,26)
		contacts = Contact.objects.filter(LastModifiedDate__gt=yesterday)
		self.assertEqual(bool(contacts.count()), True)
	
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

