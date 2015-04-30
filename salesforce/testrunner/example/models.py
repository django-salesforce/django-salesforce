# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

from __future__ import unicode_literals
from salesforce import models, DJANGO_15_PLUS
from salesforce.models import SalesforceModel as SalesforceModelParent

import django
from django.conf import settings
from django.utils.encoding import python_2_unicode_compatible

SALUTATIONS = [
	'Mr.', 'Ms.', 'Mrs.', 'Dr.', 'Prof.'
]

INDUSTRIES = [
	'Agriculture', 'Apparel', 'Banking', 'Biotechnology', 'Chemicals',
	'Communications', 'Construction', 'Consulting', 'Education',
	'Electronics', 'Energy', 'Engineering', 'Entertainment', 'Environmental',
	'Finance', 'Food & Beverage', 'Government', 'Healthcare', 'Hospitality',
	'Insurance', 'Machinery', 'Manufacturing', 'Media', 'Not For Profit',
	'Other', 'Recreation', 'Retail', 'Shipping', 'Technology',
	'Telecommunications', 'Transportation', 'Utilities'
]

# This class customizes `managed = True` for tests and does not disturbe SF
class SalesforceModel(SalesforceModelParent):
	class Meta:
		abstract = True
		managed = True


class User(SalesforceModel):
	Username = models.CharField(max_length=80)
	Email = models.CharField(max_length=100)
	LastName = models.CharField(max_length=80)
	FirstName = models.CharField(max_length=40)
	IsActive = models.BooleanField(default=False)


@python_2_unicode_compatible
class AbstractAccount(SalesforceModel):
	"""
	Default Salesforce Account model.
	"""
	TYPES = [
		'Analyst', 'Competitor', 'Customer', 'Integrator', 'Investor',
		'Partner', 'Press', 'Prospect', 'Reseller', 'Other'
	]

	Owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
			default=models.DEFAULTED_ON_CREATE,
			db_column='OwnerId')
	Type = models.CharField(max_length=100, choices=[(x, x) for x in TYPES],
							null=True)
	BillingStreet = models.CharField(max_length=255)
	BillingCity = models.CharField(max_length=40)
	BillingState = models.CharField(max_length=20)
	BillingPostalCode = models.CharField(max_length=20)
	BillingCountry = models.CharField(max_length=40)
	ShippingStreet = models.CharField(max_length=255)
	ShippingCity = models.CharField(max_length=40)
	ShippingState = models.CharField(max_length=20)
	ShippingPostalCode = models.CharField(max_length=20)
	ShippingCountry = models.CharField(max_length=40)
	Phone = models.CharField(max_length=255)
	Fax = models.CharField(max_length=255)
	Website = models.CharField(max_length=255)
	Industry = models.CharField(max_length=100,
								choices=[(x, x) for x in INDUSTRIES])
	Description = models.TextField()
	# Added read only option, otherwise the object can not be never saved
	# If the model is used also with non SF databases then there should be set
	# allow_now=True or null=True
	LastModifiedDate = models.DateTimeField(db_column='LastModifiedDate',
											sf_read_only=models.READ_ONLY,
											auto_now=True)

	class Meta(SalesforceModel.Meta):
		abstract = True

	def __str__(self):
		return self.Name


class CoreAccount(AbstractAccount):
	Name = models.CharField(max_length=255)
	class Meta(AbstractAccount.Meta):
		abstract = True


class PersonAccount(AbstractAccount):
	# Non standard fields that require activating "Person Account"
	# (irreversible changes in Salesforce)
	LastName = models.CharField(max_length=80)
	FirstName = models.CharField(max_length=40)
	Name = models.CharField(max_length=255, sf_read_only=models.READ_ONLY)
	Salutation = models.CharField(max_length=100,
								  choices=[(x, x) for x in SALUTATIONS])
	IsPersonAccount = models.BooleanField(default=False, sf_read_only=models.READ_ONLY)
	PersonEmail = models.CharField(max_length=100)

	class Meta(AbstractAccount.Meta):
		abstract = True


if getattr(settings, 'PERSON_ACCOUNT_ACTIVATED', False):
	class Account(PersonAccount):
		pass
else:
	class Account(CoreAccount):
		pass


@python_2_unicode_compatible
class Contact(SalesforceModel):
	# Example that db_column is not necessary for most of fields even with
	# lower case names and for ForeignKey
	account = models.ForeignKey(Account, on_delete=models.DO_NOTHING,
			blank=True, null=True)  # db_column: 'OwnerId'
	last_name = models.CharField(max_length=80)
	first_name = models.CharField(max_length=40, blank=True)
	name = models.CharField(max_length=121, sf_read_only=models.READ_ONLY,
			verbose_name='Full Name')
	email = models.EmailField(blank=True, null=True)
	email_bounced_date = models.DateTimeField(blank=True, null=True)
	# The `default=` with lambda function is easy readable, but can be
	# problematic with migrations in the future because it is not serializable.
	# It can be replaced by normal function.
	owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
			default=models.DEFAULTED_ON_CREATE,
			related_name='contact_owner_set')

	def __str__(self):
		return self.name


@python_2_unicode_compatible
class Lead(SalesforceModel):
	"""
	Default Salesforce Lead model.
	"""
	SOURCES = [
		'Advertisement', 'Employee Referral', 'External Referral',
		'Partner', 'Public Relations',
		'Seminar - Internal', 'Seminar - Partner', 'Trade Show', 'Web',
		'Word of mouth', 'Other',
	]

	STATUSES = [
		'Contacted', 'Open', 'Qualified', 'Unqualified',
	]

	RATINGS = [
		'Hot', 'Warm', 'Cold',
	]

	LastName = models.CharField(max_length=80)
	FirstName = models.CharField(max_length=40)
	Salutation = models.CharField(max_length=100, choices=[(x, x) for x in SALUTATIONS])
	Salutation = models.CharField(max_length=100,
								  choices=[(x, x) for x in SALUTATIONS])
	Name = models.CharField(max_length=121, sf_read_only=models.READ_ONLY)
	Title = models.CharField(max_length=128)
	Company = models.CharField(max_length=255)
	Street = models.CharField(max_length=255)
	City = models.CharField(max_length=40)
	State = models.CharField(max_length=20)
	PostalCode = models.CharField(max_length=20)
	Country = models.CharField(max_length=40)
	Phone = models.CharField(max_length=255)
	Email = models.CharField(max_length=100)
	Website = models.CharField(max_length=100)
	Description = models.TextField()
	LeadSource = models.CharField(max_length=100,
								  choices=[(x, x) for x in SOURCES])
	Status = models.CharField(max_length=100, choices=[(x, x) for x in STATUSES])
	Industry = models.CharField(max_length=100,
								  choices=[(x, x) for x in INDUSTRIES])
	Rating = models.CharField(max_length=100, choices=[(x, x) for x in RATINGS])
	# Added an example of special DateTime field in Salesforce that can
	# not be inserted, but can be updated
	# TODO write test for it
	EmailBouncedDate = models.DateTimeField(blank=True, null=True,
											sf_read_only=models.NOT_CREATEABLE)
	# Deleted object can be found only in querysets with "query_all" SF method.
	IsDeleted = models.BooleanField(default=False, sf_read_only=models.READ_ONLY)
	owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
			default=models.DEFAULTED_ON_CREATE,
			related_name='lead_owner_set')
	last_modified_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
			sf_read_only=models.READ_ONLY,
			related_name='lead_lastmodifiedby_set')

	def __str__(self):
		return self.Name


@python_2_unicode_compatible
class Product(SalesforceModel):
	Name = models.CharField(max_length=255)

	class Meta(SalesforceModel.Meta):
		db_table = 'Product2'

	def __str__(self):
		return self.Name


@python_2_unicode_compatible
class Pricebook(SalesforceModel):
	Name = models.CharField(max_length=255)

	class Meta(SalesforceModel.Meta):
		db_table = 'Pricebook2'

	def __str__(self):
		return self.Name


@python_2_unicode_compatible
class PricebookEntry(SalesforceModel):
	Name = models.CharField(max_length=255, db_column='Name', sf_read_only=models.READ_ONLY)
	Pricebook2 = models.ForeignKey('Pricebook', on_delete=models.DO_NOTHING)
	Product2 = models.ForeignKey('Product', on_delete=models.DO_NOTHING)
	UseStandardPrice = models.BooleanField(default=False)
	UnitPrice = models.DecimalField(decimal_places=2, max_digits=18)

	class Meta(SalesforceModel.Meta):
		db_table = 'PricebookEntry'
		verbose_name_plural = "PricebookEntries"

	def __str__(self):
		return self.Name


class ChargentOrder(SalesforceModel):
	class Meta(SalesforceModel.Meta):
		db_table = 'ChargentOrders__ChargentOrder__c'
		custom = True

	Name = models.CharField(max_length=255, db_column='Name')
	# example of automatically recognized name  db_column='ChargentOrders__Balance_Due__c'
	Balance_Due = models.CharField(max_length=255)


class CronTrigger(SalesforceModel):
	# A special DateTime field with milisecond resolution (read only)
	PreviousFireTime = models.DateTimeField(verbose_name='Previous Run Time', blank=True, null=True)
	# ...


class BusinessHours(SalesforceModel):
	Name = models.CharField(max_length=80)
	# The default record is automatically created by Salesforce.
	IsDefault = models.BooleanField(default=False, verbose_name='Default Business Hours')
	# ... much more fields, but we use only this one TimeFiled for test
	MondayStartTime = models.TimeField()

	class Meta:
		verbose_name_plural = "BusinessHours"


test_custom_db_table, test_custom_db_column = getattr(settings,
		'TEST_CUSTOM_FIELD', 'ChargentOrders__ChargentOrder__c.Name').split('.')

class SalesforceParentModel(SalesforceModel):
	"""
	Example of standard fields present in all custom models.
	"""
	# This is not a custom field because is not defined in a custom model.
	# The API name is therefore 'Name'.
	name = models.CharField(max_length=80)
	last_modified_date = models.DateTimeField(sf_read_only=models.READ_ONLY)
	# This model is not custom because it has not an explicit attribute
	# `custom = True` in Meta and also has not a `db_table` that ends with
	# '__c'.
	class Meta:
		abstract = True


class TestCustomExample(SalesforceParentModel):
	"""
	Simple custom model with one custom and more standard fields.

	Salesforce object for this model can be created from the branch
	  hynekcer/tooling-api-and-metadata  by commands
	$ python manage.py shell
		>> from salesforce.tooling import *
		>> install_metadata_service()
		>> create_demo_test_object()
	
	or create an object with `API Name`: `django_Test__c`
	`Data Type` of the Record Name: `Text`
	with a text field `API Name`: `TestField__c`.
	and set it accessible by you. (`Set Field-Leved Security`)
	"""
	# This is a custom field because it is defined in the custom model.
	# The API name is therefore 'TestField__c'
	test_field = models.CharField(max_length=42)
	class Meta:
		db_table = 'django_Test__c'
		custom = True


class GeneralCustomModel(SalesforceModel):
	"""
	This model is used for tests on a field of type CharField on a custom model
	specified in local_settings.py:
	Example:
		TEST_CUSTOM_FIELD = 'TIMBASURVEYS__SurveyQuestion__c.TIMBASURVEYS__Question__c'
	Other fields shouldn't be required for saving that object.
	"""
	# The line "managed = False" or Meta inherited from SalesforceModel.Meta
	# is especially important if the model shares a table with other model.
	class Meta:
		db_table = test_custom_db_table

	GeneralCustomField = models.CharField(max_length=255, db_column=test_custom_db_column)


class Note(models.Model):
	title = models.CharField(max_length=80)
	body = models.TextField(null=True)
	parent_id = models.CharField(max_length=18)
	parent_type = models.CharField(max_length=50, db_column='Parent.Type', sf_read_only=models.READ_ONLY)


class Opportunity(models.Model):
	name = models.CharField(max_length=255)
	contacts = django.db.models.ManyToManyField(Contact, through='example.OpportunityContactRole', related_name='opportunities')
	close_date = models.DateField()
	stage = models.CharField(max_length=255, db_column='StageName') # e.g. "Prospecting"


class OpportunityContactRole(models.Model):
	opportunity = models.ForeignKey(Opportunity, on_delete=models.DO_NOTHING, related_name='contact_roles')
	contact = models.ForeignKey(Contact, on_delete=models.DO_NOTHING, related_name='opportunity_roles')
	role = models.CharField(max_length=40, blank=True, null=True)  # e.g. "Business User"


class Organization(models.Model):
    name = models.CharField(max_length=80, sf_read_only=models.NOT_CREATEABLE)
    division = models.CharField(max_length=80, sf_read_only=models.NOT_CREATEABLE, blank=True)
    organization_type = models.CharField(max_length=40, verbose_name='Edition',
    		sf_read_only=models.READ_ONLY) # e.g 'Developer Edition', Enteprise, Unlimited...
    instance_name = models.CharField(max_length=5, sf_read_only=models.READ_ONLY, blank=True)
    is_sandbox = models.BooleanField(sf_read_only=models.READ_ONLY)


# Skipping the model if a custom table isn't installed in your Salesforce
# is important an old Django, even with "on_delete=DO_NOTHING",
# due to how "delete" was implemented in Django 1.4
if DJANGO_15_PLUS or getattr(settings, 'SF_TEST_TABLE_INSTALLED', False):

	class Test(models.Model):
		test_text = models.CharField(max_length=40)
		test_bool = models.BooleanField(default=False)
		contact = models.ForeignKey(Contact, null=True, on_delete=models.DO_NOTHING)
		class Meta:
			custom = True
			db_table = 'django_Test__c'


	class NoteAttachment(models.Model):
		# A standard SFDC object that can have a relationship to any custom object
		parent = models.ForeignKey(Test, sf_read_only=models.NOT_UPDATEABLE, on_delete=models.DO_NOTHING)
		title = models.CharField(max_length=80)
