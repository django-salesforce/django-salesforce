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
		BusinessHours, ChargentOrder, CronTrigger,
		GeneralCustomModel, test_custom_db_table, test_custom_db_column)

import logging
log = logging.getLogger(__name__)

DJANGO_14 = django.VERSION[:2] >= (1,4)

current_user = settings.DATABASES['salesforce']['USER']
test_email = 'test-djsf-unittests-email@example.com'
sf_tables = [x['name'] for x in
		connections['salesforce'].introspection.table_list_cache['sobjects']
		]

def refresh(obj):
	"""
	Get the same object refreshed from db.
	"""
	return obj.__class__.objects.get(pk=obj.pk)
	
def round_datetime_utc(timestamp):
	"""Round to seconds and set zone to UTC."""
	## sfdates are UTC to seconds precision but use a fixed-offset
	## of +0000 (as opposed to a named tz)
	timestamp = timestamp.replace(microsecond=0)
	if DJANGO_14:
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
		try:
			self.assertEqual(refresh(contact).EmailBouncedDate, now)
		finally:
			contact.EmailBouncedDate = old_date
			contact.save()
		self.assertEqual(refresh(contact).EmailBouncedDate, old_date)
	
	def test_insert_date(self):
		"""
		Test inserting a date.
		"""
		now = round_datetime_utc(datetime.datetime.utcnow())
		contact = Contact(
				FirstName = 'Joe',
				LastName = 'Freelancer',
				EmailBouncedDate=now.replace(tzinfo=pytz.utc))
		contact.save()
		try:
			self.assertEqual(refresh(contact).EmailBouncedDate, now)
		finally:
			contact.delete()

	def test_default_specified_by_sf(self):
		"""
		Verify that an object with a field with default value specified by some
		Salesforce code can be inserted. (The default is used only for a field
		unspecified in SF REST API, but not for None or any similar value.
		It was a pain for some unimportant foreign keys that don't accept null.
		"""
		# Verify a smart default is used.
		contact = Contact(FirstName = 'sf_test', LastName='my')
		contact.save()
		try:
			self.assertEqual(refresh(contact).Owner.Username, current_user)
		finally:
			contact.delete()
		# Verify that an explicit value is possible for this field.
		other_user_obj = User.objects.exclude(Username=current_user)[0]
		contact = Contact(FirstName = 'sf_test', LastName='your',
				Owner=other_user_obj)
		contact.save()
		try:
			self.assertEqual(
					refresh(contact).Owner.Username, other_user_obj.Username)
		finally:
			contact.delete()
	
	def test_get(self):
		"""
		Get the test lead record.
		"""
		lead = Lead.objects.get(Email=test_email)
		self.assertEqual(lead.FirstName, 'User')
		self.assertEqual(lead.LastName, 'Unittest General')
		# test a read only field (formula of full name)
		self.assertEqual(lead.Name, 'User Unittest General')
	
	def test_not_null(self):
		"""
		Get the test lead record by isnull condition.
		"""
		# TODO similar failed: Contact.objects.filter(Account__isnull=True)
		#              passed: Contact.objects.filter(Account=None)
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
		try:
			self.assertEqual(refresh(test_lead).FirstName, u'\u2603')
		finally:
			test_lead.delete()
	
	def test_date_comparison(self):
		"""
		Test that date comparisons work properly.
		"""
		today = round_datetime_utc(datetime.datetime(2013, 8, 27))
		yesterday = today - datetime.timedelta(days=1)
		tomorrow = today + datetime.timedelta(days=1)
		contact = Contact(FirstName='sf_test', LastName='date',
				EmailBouncedDate=today)
		contact.save()
		try:
			contacts1 = Contact.objects.filter(EmailBouncedDate__gt=yesterday)
			self.assertEqual(len(contacts1), 1)
			contacts2 = Contact.objects.filter(EmailBouncedDate__gt=tomorrow)
			self.assertEqual(len(contacts2), 0)
		finally:
			contact.delete()
	
	def test_insert(self):
		"""
		Create a lead record, and make sure it ends up with a valid Salesforce ID.
		"""
		test_lead = Lead(FirstName="User", LastName="Unittest Inserts",
				Email='test-djsf-inserts-email@example.com',
				Company="Some company")
		test_lead.save()
		try:
			self.assertEqual(len(test_lead.pk), 18)
		finally:
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
		self.assertEqual(refresh(test_lead).FirstName, 'Tested')

	def test_custom_objects(self):
		"""
		Make sure custom objects work.
		"""
		if not 'ChargentOrders__ChargentOrder__c' in sf_tables:
			self.skipTest('Not found custom tables ChargentOrders__*')
		orders = ChargentOrder.objects.all()[0:5]
		self.assertEqual(len(orders), 5)

	def test_custom_object_general(self):
		"""
		Create, read and delete any general custom object.
		Object name and field name are user configurable by TEST_CUSTOM_FIELD.
		"""
		table_list_cache = connections['salesforce'].introspection.table_list_cache
		table_names = [x['name'] for x in table_list_cache['sobjects']]
		if not test_custom_db_table in sf_tables:
			self.skipTest("Not found the expected custom object '%s'" %
					test_custom_db_table)
		obj = GeneralCustomModel(GeneralCustomField='sf_test')
		obj.save()
		try:
			results = GeneralCustomModel.objects.all()[0:1]
			self.assertEqual(len(results), 1)
			self.assertEqual(results[0].GeneralCustomField, 'sf_test')
		finally:
			obj.delete()

	def test_datetime_miliseconds(self):
		"""
		Verify that a field with milisecond resolution is readable.
		"""
		trigger = CronTrigger.objects.all()[0]
		self.assertTrue(isinstance(trigger.PreviousFireTime, datetime.datetime))
		# The reliability of this is only 99.9%, therefore it is commented out.
		#self.assertNotEqual(trigger.PreviousFireTime.microsecond, 0)

	def test_time_field(self):
		"""
		Test a TimeField (read, modify, verify).
		"""
		obj_orig = BusinessHours.objects.all()[0]
		obj = refresh(obj_orig)
		self.assertTrue(isinstance(obj.MondayStartTime, datetime.time))
		obj.MondayStartTime = datetime.time(23, 59)
		obj.save()
		obj = refresh(obj)
		try:
			self.assertEqual(obj.MondayStartTime, datetime.time(23, 59))
		finally:
			obj_orig.save()

	def test_account_insert_delete(self):
		"""
		Test insert and delete an account (normal or personal SF config)
		"""
		if settings.PERSON_ACCOUNT_ACTIVATED:
			test_account = Account(FirstName='IntegrationTest',
					LastName='Account')
		else:
			test_account = Account(Name='IntegrationTest Account')
		test_account.save()
		try:
			accounts = Account.objects.filter(Name='IntegrationTest Account')
			self.assertEqual(len(accounts), 1)
		finally:
			test_account.delete()

	def test_similarity_filter_operators(self):
		"""
		Test filter operators that use LIKE 'something%' and similar.
		"""
		User.objects.get(Username__exact=current_user)
		User.objects.get(Username__iexact=current_user.upper())
		User.objects.get(Username__contains=current_user[1:-1])
		User.objects.get(Username__icontains=current_user[1:-1].upper())
		User.objects.get(Username__startswith=current_user[:-1])
		User.objects.get(Username__istartswith=current_user[:-1].upper())
		User.objects.get(Username__endswith=current_user[1:])
		User.objects.get(Username__iendswith=current_user[1:].upper())
		# Operators regex and iregex not tested because they are not supported.

	def test_unsupported_bulk_create(self):
		"""
		Unsupported bulk_create: "Errors should never pass silently."
		"""
		if not DJANGO_14:
			self.skipTest('Django 1.3 has no bulk operations.')
		objects = [Contact(LastName='sf_test a'), Contact(LastName='sf_test b')]
		self.assertRaises(AssertionError, Contact.objects.bulk_create, objects)
