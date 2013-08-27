# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

import datetime
import pytz

from django.conf import settings
from django.db import connections
from django.test import TestCase
import django

from salesforce.testrunner.example.models import (Contact, Lead, User,
		ChargentOrder)

import logging
log = logging.getLogger(__name__)

current_user = settings.DATABASES['salesforce']['USER']
test_email = 'test-djsf-unittests-email@example.com'
sf_tables = [x['name'] for x in
		connections['salesforce'].introspection.table_list_cache['sobjects']
		]

def round_datetime_utc(timestamp):
	"""Round to seconds and set zone to UTC."""
	timestamp -= datetime.timedelta(microseconds=timestamp.microsecond)
	if django.VERSION[:2] >= (1,4):
		timestamp= timestamp.replace(tzinfo=pytz.utc)
	return timestamp


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
	
	def test_raw(self):
		"""
		Get the first two contact records.
		"""
		contacts = Contact.objects.raw(
				"SELECT Id, LastName, FirstName FROM Contact "
				"LIMIT 2")
		self.assertEqual(len(contacts), 2)
		'%s' % contacts[0].__dict__  # Check that all fields are accessible
	
	def test_raw_foreignkey_id(self):
		"""
		Get the first two contacts by raw query with a ForeignKey id field.
		"""
		contacts = Contact.objects.raw(
				"SELECT Id, LastName, FirstName, OwnerId FROM Contact "
				"LIMIT 2")
		self.assertEqual(len(contacts), 2)
		'%s' % contacts[0].__dict__  # Check that all fields are accessible
		self.assertIn('@', contacts[0].Owner.Email)
	
	def test_select_all(self):
		"""
		Get the first two contact records.
		"""
		contacts = Contact.objects.all()[0:2]
		self.assertEqual(len(contacts), 2)
	
	def test_foreign_key(self):
		"""
		Verify that the owner of an Contact is the currently logged admin.
		"""
		contact = Contact.objects.all()[0]
		user = contact.Owner
		# This user can be e.g. 'admins@freelancersunion.org.prod001'.
		self.assertEqual(user.Username, current_user)
	
	def test_update_date(self):
		"""
		Test updating a date.
		"""
		now = round_datetime_utc(datetime.datetime.now())
		contact = Contact.objects.all()[0]
		old_date = contact.EmailBouncedDate
		contact.EmailBouncedDate = now
		contact.save()
		# test
		saved = Contact.objects.get(pk=contact.pk)
		self.assertEqual(saved.EmailBouncedDate, now)
		# restore
		saved.EmailBouncedDate = old_date 
		saved.save()
	
	def test_insert_date(self):
		"""
		Test inserting a date.
		"""
		now = round_datetime_utc(datetime.datetime.now())
		contact = Contact(
			FirstName = 'Joe',
			LastName = 'Freelancer',
			Owner=User.objects.get(Username=current_user),
			EmailBouncedDate=now,
		)
		contact.save()
		# test
		saved = Contact.objects.get(pk=contact.pk)
		self.assertEqual(saved.EmailBouncedDate, (now))
		# restore
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
		test_lead = Lead(FirstName=u'\u2603', LastName="Unittest Unicode",
				Email='test-djsf-unicode-email@example.com',
				Company="Some company")
		test_lead.save()
		self.assertEqual(test_lead.FirstName, u'\u2603')
		test_lead.delete()
	
	def test_date_comparison(self):
		"""
		Test that date comparisons work properly.
		"""
		today = round_datetime_utc(datetime.datetime(2013, 8, 27))
		yesterday = today - datetime.timedelta(days=1)
		tomorrow = today + datetime.timedelta(days=1)
		contact = Contact(FirstName='sf_test', LastName='date',
				Owner=User.objects.get(Username=current_user),
				EmailBouncedDate=today)
		contact.save()
		contact = Contact.objects.get(pk=contact.pk)
		contacts = Contact.objects.filter(EmailBouncedDate__gt=yesterday)
		self.assertEqual(contacts.count(), 1)
		contacts = Contact.objects.filter(EmailBouncedDate__gt=tomorrow)
		self.assertEqual(contacts.count(), 0)
		contact.delete()
	
	def test_insert(self):
		"""
		Create a lead record, and make sure it ends up with a valid Salesforce ID.
		"""
		test_lead = Lead(FirstName="User", LastName="Unittest Inserts",
				Email='test-djsf-inserts-email@example.com',
				Company="Some company")
		test_lead.save()
		self.assertEqual(len(test_lead.pk), 18)
		test_lead.delete()
	
	def test_delete(self):
		"""
		Create a lead record, then delete it, and make sure it's gone.
		"""
		test_lead = Lead(FirstName="User", LastName="Unittest Deletes",
				Email='test-djsf-delete-email@example.com',
				Company="Some company")
		test_lead.save()
		test_lead.delete()
		
		self.assertRaises(Lead.DoesNotExist, Lead.objects.get, Email='test-djsf-delete-email@example.com')
	
	def test_update(self):
		"""
		Update the test lead record.
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
		if not 'ChargentOrders__ChargentOrder__c' in sf_tables:
			self.skipTest('Not found custom tables ChargentOrders__*')
		orders = ChargentOrder.objects.all()[0:5]
		self.assertEqual(len(orders), 5)

