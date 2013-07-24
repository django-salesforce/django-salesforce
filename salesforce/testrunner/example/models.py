# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

from django.db import models

from salesforce.models import SalesforceModel

SALUTATIONS = [
	'Mr.', 'Ms.', 'Mrs.', 'Dr.', 'Prof.'
]

INDUSTRIES = [
	'Agriculture', 'Apparel', 'Banking', 'Biotechnology', 'Chemicals',
	'Communications', 'Construction', 'Consulting', 'Education',
	'Electronics', 'Energy', 'Engineering', 'Entertainment', 'Environmental',
	'Finance', 'Food & Beverage', 'Government', 'Healthcare', 'Hospitality',
	'Insurance', 'Machinery', 'Manufacturing', 'Media', 'Not For Profit',
	'Other', 'Recreation', 'Retail', 'Shipping', 'Technology', 'Telecommunications',
	'Transportation', 'Utilities'
]

class User(SalesforceModel):
	Email = models.CharField(max_length=100)
	LastName = models.CharField(max_length=80)
	FirstName = models.CharField(max_length=40)
	IsActive = models.BooleanField()

class Account(SalesforceModel):
	"""
	Default Salesforce Account model.
	"""
	TYPES = [
		'Analyst', 'Competitor', 'Customer', 'Integrator', 'Investor',
		'Partner', 'Press', 'Prospect', 'Reseller', 'Other'
	]
	
	Name = models.CharField(max_length=255)
	Owner = models.ForeignKey(User, db_column='OwnerId')
	#LastName = models.CharField(max_length=80)
	#FirstName = models.CharField(max_length=40)
	#Salutation = models.CharField(max_length=100, choices=[(x, x) for x in SALUTATIONS])
	Type = models.CharField(max_length=100, choices=[(x, x) for x in TYPES])
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
	Industry = models.CharField(max_length=100, choices=[(x, x) for x in INDUSTRIES])
	Description = models.TextField()
	#IsPersonAccount = models.BooleanField()
	#PersonEmail = models.CharField(max_length=100)
	LastModifiedDate = models.DateTimeField(db_column='LastModifiedDate')
	
	def __unicode__(self):
		return self.FirstName + ' ' + self.LastName

class Lead(SalesforceModel):
	"""
	Default Salesforce Lead model.
	"""
	SOURCES = [
		'Advertisement', 'Employee Referral', 'External Referral', 'Partner', 'Public Relations',
		'Seminar - Internal', 'Seminar - Partner', 'Trade Show', 'Web', 'Word of mouth', 'Other',
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
	#Name = models.CharField(max_length=121)
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
	LeadSource = models.CharField(max_length=100, choices=[(x, x) for x in SOURCES])
	Status = models.CharField(max_length=100, choices=[(x, x) for x in STATUSES])
	Industry = models.CharField(max_length=100, choices=[(x, x) for x in INDUSTRIES])
	Rating = models.CharField(max_length=100, choices=[(x, x) for x in RATINGS])
	
	def __unicode__(self):
		return self.FirstName + ' ' + self.LastName

class TimbaSurveysQuestion(SalesforceModel):
        class Meta:
                db_table = 'TIMBASURVEYS__SurveyQuestion__c'

        Question = models.CharField(max_length=255, db_column='TIMBASURVEYS__Question__c')
        # ...


class Contact(SalesforceModel):
        class Meta:
                db_table = 'Contact'
        LastName = models.CharField(max_length=255, db_column='LastName')

class Email(SalesforceModel):
        class Meta:
                db_table = 'Email__c'

        #name = models.CharField(max_length=240, db_column=u'Name', editable=False)
        Account = models.ForeignKey(Account, db_column='Account__c')
        Contact = models.ForeignKey(Contact, db_column='Contact__c')
        Email = models.CharField(max_length=255, db_column='Email__c')
        LastUsedDate = models.DateTimeField(null=True, db_column='Last_Used_Date__c', blank=True)

import pdb; pdb.set_trace()
class ChargentOrder(SalesforceModel):
	class Meta:
		db_table = 'ChargentOrders__ChargentOrder__c'
	
	OwnerId = models.CharField(max_length=255, db_column='OwnerId')
	IsDeleted = models.CharField(max_length=255, db_column='IsDeleted')
	Name = models.CharField(max_length=255, db_column='Name')
	CreatedDate = models.CharField(max_length=255, db_column='CreatedDate')
	CreatedById = models.CharField(max_length=255, db_column='CreatedById')
	LastModifiedDate = models.CharField(max_length=255, db_column='LastModifiedDate')
	LastModifiedById = models.CharField(max_length=255, db_column='LastModifiedById')
	SystemModstamp = models.CharField(max_length=255, db_column='SystemModstamp')
	LastActivityDate = models.CharField(max_length=255, db_column='LastActivityDate')
	Balance_Due = models.CharField(max_length=255, db_column='ChargentOrders__Balance_Due__c')
	Bank_Account_Name = models.CharField(max_length=255, db_column='ChargentOrders__Bank_Account_Name__c')
	Bank_Account_Number = models.CharField(max_length=255, db_column='ChargentOrders__Bank_Account_Number__c')
	Bank_Account_Type = models.CharField(max_length=255, db_column='ChargentOrders__Bank_Account_Type__c')
	Bank_Name = models.CharField(max_length=255, db_column='ChargentOrders__Bank_Name__c')
	Bank_Routing_Number = models.CharField(max_length=255, db_column='ChargentOrders__Bank_Routing_Number__c')
	Billing_Address = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Address__c')
	Billing_City = models.CharField(max_length=255, db_column='ChargentOrders__Billing_City__c')
	Billing_Company = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Company__c')
	Billing_Country = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Country__c')
	Billing_Email = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Email__c')
	Billing_Fax = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Fax__c')
	Billing_First_Name = models.CharField(max_length=255, db_column='ChargentOrders__Billing_First_Name__c')
	Billing_Last_Name = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Last_Name__c')
	Billing_Phone = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Phone__c')
	Billing_State_Province = models.CharField(max_length=255, db_column='ChargentOrders__Billing_State_Province__c')
	Billing_State = models.CharField(max_length=255, db_column='ChargentOrders__Billing_State__c')
	Billing_Zip_Postal = models.CharField(max_length=255, db_column='ChargentOrders__Billing_Zip_Postal__c')
	Birthdate = models.CharField(max_length=255, db_column='ChargentOrders__Birthdate__c')
	Card_Expiration_Month = models.CharField(max_length=255, db_column='ChargentOrders__Card_Expiration_Month__c')
	Card_Expiration_Year = models.CharField(max_length=255, db_column='ChargentOrders__Card_Expiration_Year__c')
	Card_Number = models.CharField(max_length=255, db_column='ChargentOrders__Card_Number__c')
	Card_Security_Code = models.CharField(max_length=255, db_column='ChargentOrders__Card_Security_Code__c')
	Card_Type = models.CharField(max_length=255, db_column='ChargentOrders__Card_Type__c')
	Charge_Amount = models.CharField(max_length=255, db_column='ChargentOrders__Charge_Amount__c')
	Check_Number = models.CharField(max_length=255, db_column='ChargentOrders__Check_Number__c')
	Credit_Card_Name = models.CharField(max_length=255, db_column='ChargentOrders__Credit_Card_Name__c')
	Currency = models.CharField(max_length=255, db_column='ChargentOrders__Currency__c')
	Date = models.CharField(max_length=255, db_column='ChargentOrders__Date__c')
	Description = models.CharField(max_length=255, db_column='ChargentOrders__Description__c')
	Gateway = models.CharField(max_length=255, db_column='ChargentOrders__Gateway__c')
	Manual_Charge = models.CharField(max_length=255, db_column='ChargentOrders__Manual_Charge__c')
	Mercury_ID = models.CharField(max_length=255, db_column='ChargentOrders__Mercury_ID__c')
	No_Tax = models.CharField(max_length=255, db_column='ChargentOrders__No_Tax__c')
	OrderNumber = models.CharField(max_length=255, db_column='ChargentOrders__OrderNumber__c')
	Order_Note = models.CharField(max_length=255, db_column='ChargentOrders__Order_Note__c')
	PO_Number = models.CharField(max_length=255, db_column='ChargentOrders__PO_Number__c')
	Payment_Count = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Count__c')
	Payment_End_Date = models.CharField(max_length=255, db_column='ChargentOrders__Payment_End_Date__c')
	Payment_Frequency = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Frequency__c')
	Payment_Method = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Method__c')
	Payment_Received = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Received__c')
	Payment_Start_Date = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Start_Date__c')
	Payment_Status = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Status__c')
	Payment_Stop = models.CharField(max_length=255, db_column='ChargentOrders__Payment_Stop__c')
	Shipping_Address = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Address__c')
	Shipping_City = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_City__c')
	Shipping_Company = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Company__c')
	Shipping_Country = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Country__c')
	Shipping_Duty = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Duty__c')
	Shipping_First_Name = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_First_Name__c')
	Shipping_Instructions = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Instructions__c')
	Shipping_Name = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Name__c')
	Shipping_Phone = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Phone__c')
	Shipping_State = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_State__c')
	Shipping_Zip_Postal = models.CharField(max_length=255, db_column='ChargentOrders__Shipping_Zip_Postal__c')
	Shipping = models.CharField(max_length=255, db_column='ChargentOrders__Shipping__c')
	Status = models.CharField(max_length=255, db_column='ChargentOrders__Status__c')
	Subtotal = models.CharField(max_length=255, db_column='ChargentOrders__Subtotal__c')
	Tax_Exempt = models.CharField(max_length=255, db_column='ChargentOrders__Tax_Exempt__c')
	Tax = models.CharField(max_length=255, db_column='ChargentOrders__Tax__c')
	Total = models.CharField(max_length=255, db_column='ChargentOrders__Total__c')
	Tracking_Number = models.CharField(max_length=255, db_column='ChargentOrders__Tracking_Number__c')
	Transaction_Count_Recurring = models.CharField(max_length=255, db_column='ChargentOrders__Transaction_Count_Recurring__c')
	Transaction_Count = models.CharField(max_length=255, db_column='ChargentOrders__Transaction_Count__c')
	Transaction_Total = models.CharField(max_length=255, db_column='ChargentOrders__Transaction_Total__c')
	AccountID = models.CharField(max_length=255, db_column='AccountID__c')
	Campaign = models.CharField(max_length=255, db_column='Campaign__c')
	Contribution_Date = models.CharField(max_length=255, db_column='Contribution_Date__c')
	Contribution_Type = models.CharField(max_length=255, db_column='Contribution_Type__c')
	Corporate_Flag = models.CharField(max_length=255, db_column='Corporate_Flag__c')
	Follow_up_Complete = models.CharField(max_length=255, db_column='Follow_up_Complete__c')
	Member_Flag = models.CharField(max_length=255, db_column='Member_Flag__c')
	Opportunity = models.CharField(max_length=255, db_column='Opportunity__c')
	Order_Name = models.CharField(max_length=255, db_column='Order_Name__c')
	PAC_Fund = models.CharField(max_length=255, db_column='PAC_Fund__c')
	Event_Flag = models.CharField(max_length=255, db_column='Event_Flag__c')
