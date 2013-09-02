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

from salesforce.testrunner.example.models import (Account, Contact, Lead, User,
		BusinessHours, ChargentOrder, CronTrigger)

import logging
log = logging.getLogger(__name__)

current_user = settings.DATABASES['salesforce']['USER']
test_email = 'test-djsf-unittests-email@example.com'
sf_tables = [x['name'] for x in
		connections['salesforce'].introspection.table_list_cache['sobjects']
		]

def round_datetime_utc(timestamp):
	"""Round to seconds and set zone to UTC."""
	## sfdates are UTC to seconds precision but use a fixed-offset
	## of +0000 (as opposed to a named tz)
	timestamp = timestamp.replace(microsecond=0)
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
		now = round_datetime_utc(datetime.datetime.utcnow())
		contact = Contact.objects.all()[0]
		old_date = contact.EmailBouncedDate
		contact.EmailBouncedDate = now.replace(tzinfo=pytz.utc)
		contact.save()
		# get, restore, test
		saved = Contact.objects.get(pk=contact.pk)
		contact.EmailBouncedDate = old_date
		contact.save()
		self.assertEqual(saved.EmailBouncedDate, now)
	
	def test_insert_date(self):
		"""
		Test inserting a date.
		"""
		now = round_datetime_utc(datetime.datetime.utcnow())
		contact = Contact(
			FirstName = 'Joe',
			LastName = 'Freelancer',
			Owner=User.objects.get(Username=current_user),
			EmailBouncedDate=now.replace(tzinfo=pytz.utc),
		)
		contact.save()
		# get, restore, test
		saved = Contact.objects.get(pk=contact.pk)
		saved.delete()
		self.assertEqual(saved.EmailBouncedDate, (now))
	
	def test_get(self):
		"""
		Get the test lead record.
		"""
		lead = Lead.objects.get(Email=test_email)
		self.assertEqual(lead.FirstName, 'User')
		self.assertEqual(lead.LastName, 'Unittest General')
		self.assertEqual(lead.Name, 'User Unittest General')
	
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
		test_lead.delete()
		self.assertEqual(test_lead.FirstName, u'\u2603')
	
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
		contacts1 = list(Contact.objects.filter(EmailBouncedDate__gt=yesterday))
		contacts2 = list(Contact.objects.filter(EmailBouncedDate__gt=tomorrow))
		contact.delete()
		self.assertEqual(len(contacts1), 1)
		self.assertEqual(len(contacts2), 0)
	
	def test_insert(self):
		"""
		Create a lead record, and make sure it ends up with a valid Salesforce ID.
		"""
		test_lead = Lead(FirstName="User", LastName="Unittest Inserts",
				Email='test-djsf-inserts-email@example.com',
				Company="Some company")
		test_lead.save()
		pk = test_lead.pk
		test_lead.delete()
		self.assertEqual(len(pk), 18)
	
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

	def test_datetime_miliseconds(self):
		"""
		Verify that it accepts a field with milisecond resolution.
		"""
		trigger = CronTrigger.objects.all()[0]
		self.assertTrue(isinstance(trigger.PreviousFireTime, datetime.datetime))
		# The reliability of this is only 99.9%, therefore it is commented out.
		#self.assertNotEqual(trigger.PreviousFireTime.microsecond, 0)

	def test_time_field(self):
		"""
		Test a TimeField (read, modify, verify, restore the original).
		"""
		obj_orig = BusinessHours.objects.all()[0]
		self.assertTrue(isinstance(obj_orig.MondayStartTime, datetime.time))
		obj = BusinessHours.objects.get(pk=obj_orig.pk)
		obj.MondayStartTime = datetime.time(23, 59)
		obj.save()
		self.assertEqual(obj.MondayStartTime, datetime.time(23, 59))
		obj_orig.save()

	def test_account_insert_delete(self):
		"""
		Test insert and delete an account (normal or personal SF config)
		"""
		if settings.PERSON_ACCOUNT_ACTIVATED:
			test_account = Account(FirstName='IntegrationTest',
					LastName='Account',
					Owner=User.objects.get(Username=current_user))
		else:
			test_account = Account(Name='IntegrationTest Account',
					Owner=User.objects.get(Username=current_user))
		test_account.save()
		account_list = list(Account.objects.filter(Name='IntegrationTest Account'))
		test_account.delete()
		self.assertEqual(len(account_list), 1)

	def test_select_like_operators(self):
		"""
		Test operators that use LIKE 'something%' and similar.
		"""
		User.objects.get(Username__exact=current_user)
		User.objects.get(Username__iexact=current_user.upper())
		User.objects.get(Username__contains=current_user[1:-1])
		User.objects.get(Username__icontains=current_user[1:-1].upper())
		User.objects.get(Username__startswith=current_user[:-1])
		User.objects.get(Username__istartswith=current_user[:-1].upper())
		User.objects.get(Username__endswith=current_user[1:])
		User.objects.get(Username__iendswith=current_user[1:].upper())
		# NOT TESTED regex, iregex because they are not supported
