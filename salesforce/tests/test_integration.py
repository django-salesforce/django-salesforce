# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

from decimal import Decimal
import datetime
import pytz
import random
import string

from django.conf import settings
from django.db import connections
from django.db.models import Q, Avg, Count, Sum, Min, Max
from django.test import TestCase
from django.utils.unittest import skip, skipUnless

from salesforce.testrunner.example.models import (Account, Contact, Lead, User,
		BusinessHours, ChargentOrder, CronTrigger,
		Product, Pricebook, PricebookEntry,
		GeneralCustomModel, test_custom_db_table, test_custom_db_column)
from salesforce import router, DJANGO_15
from salesforce.backend import sf_alias

import logging
log = logging.getLogger(__name__)

random_slug = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for x in range(32))
current_user = settings.DATABASES['salesforce']['USER']
test_email = 'test-djsf-unittests-%s@example.com' % random_slug
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
	timestamp = timestamp.replace(tzinfo=pytz.utc)
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
		(At least 3 manually created Contacts must exist before these read-only tests.)
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

	def test_exclude_query_construction(self):
		"""
		Test that exclude query construction returns valid SOQL.
		"""
		contacts = Contact.objects.filter(FirstName__isnull=False).exclude(Email="steve@apple.com", LastName="Wozniak").exclude(LastName="smith")
		number_of_contacts = contacts.count()
		self.assertIsInstance(number_of_contacts, int)
		# the default self.test_lead shouldn't be excluded by only one nondition
		leads = Lead.objects.exclude(Email="steve@apple.com", LastName="Unittest General").filter(FirstName="User", LastName="Unittest General")
		self.assertEqual(leads.count(), 1)

	def test_foreign_key(self):
		"""
		Verify that the owner of an Contact is the currently logged admin.
		"""
		current_sf_user = User.objects.get(Username=current_user)
		test_contact = Contact(FirstName = 'sf_test', LastName='my')
		test_contact.save()
		try:
			contact = Contact.objects.filter(Owner=current_sf_user)[0]
			user = contact.Owner
			# This user can be e.g. 'admins@freelancersunion.org.prod001'.
			self.assertEqual(user.Username, current_user)
		finally:
			test_contact.delete()

	def test_foreign_key_column(self):
		"""
		Verify filtering by a column of related parent object.
		"""
		test_account = Account(Name = 'sf_test account')
		test_account.save()
		test_contact = Contact(FirstName = 'sf_test', LastName='my', Account=test_account)
		test_contact.save()
		try:
			contacts = Contact.objects.filter(Account__Name='sf_test account')
			self.assertEqual(len(contacts), 1)
		finally:
			test_contact.delete()
			test_account.delete()

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
		lead = Lead.objects.get(Email__isnull=False, FirstName='User')
		self.assertEqual(lead.FirstName, 'User')
		self.assertEqual(lead.LastName, 'Unittest General')
	
	def test_not_null_related(self):
		"""
		Verify conditions `isnull` for foreign keys: filter(Account=None)
		filter(Account__isnull=True) and nested in Q(...) | Q(...).
		"""
		test_contact = Contact(FirstName='sf_test', LastName='my')
		test_contact.save()
		try:
			contacts = Contact.objects.filter(Q(Account__isnull=True) |
					Q(Account=None), Account=None, Account__isnull=True,
					FirstName='sf_test')
			self.assertEqual(len(contacts), 1)
		finally:
			test_contact.delete()
	
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
		self.assertEqual(test_lead.FirstName, 'User')
		test_lead.FirstName = 'Tested'
		test_lead.save()
		self.assertEqual(refresh(test_lead).FirstName, 'Tested')

	def test_decimal_precision(self):
		"""
		Ensure that the precision on a DecimalField of a record saved to
		or retrieved from SalesForce is equal.
		"""
		product = Product(Name="Test Product")
		product.save()

		# The price for a product must be set in the standard price book.
		# http://www.salesforce.com/us/developer/docs/api/Content/sforce_api_objects_pricebookentry.htm
		pricebook = Pricebook.objects.get(Name="Standard Price Book")
		saved_pricebook_entry = PricebookEntry(Product2Id=product, Pricebook2Id=pricebook, UnitPrice=Decimal('1234.56'), UseStandardPrice=False)
		saved_pricebook_entry.save()
		retrieved_pricebook_entry = PricebookEntry.objects.get(pk=saved_pricebook_entry.pk)

		try:
			self.assertEqual(saved_pricebook_entry.UnitPrice, retrieved_pricebook_entry.UnitPrice)
		finally:
			retrieved_pricebook_entry.delete()
			product.delete()

	@skipUnless('ChargentOrders__ChargentOrder__c' in sf_tables,
			'Not found custom tables ChargentOrders__*')
	def test_custom_objects(self):
		"""
		Make sure custom objects work.
		"""
		orders = ChargentOrder.objects.all()[0:5]
		self.assertEqual(len(orders), 5)

	@skipUnless(test_custom_db_table in sf_tables,
			"Not found the expected custom object '%s'" % test_custom_db_table)
	def test_custom_object_general(self):
		"""
		Create, read and delete any general custom object.
		Object name and field name are user configurable by TEST_CUSTOM_FIELD.
		"""
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
		triggers = CronTrigger.objects.all()
		if not triggers:
			self.skipTest("No object with milisecond resolution found.")
		self.assertTrue(isinstance(triggers[0].PreviousFireTime, datetime.datetime))
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
		objects = [Contact(LastName='sf_test a'), Contact(LastName='sf_test b')]
		self.assertRaises(AssertionError, Contact.objects.bulk_create, objects)

	def test_escape_single_quote(self):
		"""
		Test that single quotes in strings used in filtering a QuerySet
		are escaped properly.
		"""
		account_name = '''Dr. Evil's Giant "Laser", LLC'''
		account = Account(Name=account_name)
		account.save()
		try:
			self.assertTrue(Account.objects.filter(Name=account_name).exists())
		finally:
			account.delete()

	def test_escape_single_quote_in_raw_query(self):
		"""
		Test that manual escaping within a raw query is not double escaped.
		"""
		account_name = '''Dr. Evil's Giant "Laser", LLC'''
		account = Account(Name=account_name)
		account.save()

		manually_escaped = '''Dr. Evil\\'s Giant "Laser", LLC'''
		try:
			retrieved_account = Account.objects.raw(
				"SELECT Id, Name FROM Account WHERE Name = '%s'" % manually_escaped)[0]
			self.assertEqual(account_name, retrieved_account.Name)
		finally:
			account.delete()

	def test_raw_query_empty(self):
		"""
		Test that the raw query works even for queries with empty results.
		"""
		len(list(Contact.objects.raw("SELECT Id, FirstName FROM Contact WHERE FirstName='nonsense'")))

	def test_combined_international(self):
		"""
		Test combined filters with international characters.
		"""
		# This is OK for long time
		len(Contact.objects.filter(Q(FirstName=u'\xe1') & Q(LastName=u'\xe9')))
		# This was recently fixed
		len(Contact.objects.filter(Q(FirstName=u'\xe1') | Q(LastName=u'\xe9')))
		len(Contact.objects.filter(Q(FirstName='\xc3\xa1') | Q(LastName='\xc3\xa9')))

	def test_aggregate_query(self):
		"""
		Test for different aggregate function.
		"""
		test_product = Product(Name='test soap')
		test_product.save()
		test_product2 = Product(Name='test brush')
		test_product2.save()
		pricebook = Pricebook.objects.get(Name="Standard Price Book")
		PricebookEntry(Product2Id=test_product, Pricebook2Id=pricebook,
				UseStandardPrice=False, UnitPrice=Decimal(100)).save()
		PricebookEntry(Product2Id=test_product2, Pricebook2Id=pricebook,
				UseStandardPrice=False, UnitPrice=Decimal(80)).save()
		try:
			x_products = PricebookEntry.objects.filter(Name__startswith='test ')
			result = x_products.aggregate(Sum('UnitPrice'), Count('UnitPrice'), Avg('UnitPrice'), Min('UnitPrice'))
			self.assertDictEqual(result, {'UnitPrice__sum': 180, 'UnitPrice__count': 2, 'UnitPrice__avg': 90.0, 'UnitPrice__min': 80})
		finally:
			# dependent PricebookEntries are just deleted automatically by SF
			test_product.delete()
			test_product2.delete()

	@skipUnless(DJANGO_15, "the parameter 'update_fields' requires Django 1.5+")
	def test_save_update_fields(self):
		"""
		Test the save method with parameter `update_fields`
		that updates only required fields.
		"""
		company_orig = self.test_lead.Company
		self.test_lead.Company = 'A'  # TODO None
		self.test_lead.FirstName = 'John'
		self.test_lead.save(update_fields=['FirstName'])
		test_lead = refresh(self.test_lead)
		self.assertEqual(test_lead.FirstName, 'John')
		self.assertEqual(test_lead.Company, company_orig)

	#@skip("Waiting for bug fix")
