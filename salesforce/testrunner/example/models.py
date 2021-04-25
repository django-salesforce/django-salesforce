"""
This model file is copied from:

django-salesforce

by Phil Christensen
(c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
See LICENSE.md for details

We are using it to create a custom data model of the patient connections platform, which is the core operating system
for Lilly's customer support programs. This will allow us to add object models, manipulate them through code and
perform custom queries that are displayed directly into a web framework: Django.

@author Preston Mackert
"""


# -------------------------------------------------------------------------------------------------------------------- #
# imports
# -------------------------------------------------------------------------------------------------------------------- #

from typing import Optional
import types

import django
from django.utils import timezone
from django.conf import settings
from django.db import models
from phone_field import PhoneField

from salesforce import models
from salesforce.models import SalesforceModel as SalesforceModelParent

# -------------------------------------------------------------------------------------------------------------------- #
# i think these are global definitions
# -------------------------------------------------------------------------------------------------------------------- #

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

# -------------------------------------------------------------------------------------------------------------------- #
# defining these models from SFDC, the standard objects seem to be provided
# -------------------------------------------------------------------------------------------------------------------- #

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
    UserType = models.CharField(max_length=80)


class AbstractAccount(SalesforceModel):
    """
    Default Salesforce Account model.
    """
    TYPES = [
        'Analyst', 'Competitor', 'Customer', 'Integrator', 'Investor',
        'Partner', 'Press', 'Prospect', 'Reseller', 'Other'
    ]

    Owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                              default=models.DefaultedOnCreate(User),
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
        return self.Name  # pylint: disable=no-member


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
    class Account(PersonAccount):  # pylint:disable=model-no-explicit-unicode
        pass
else:
    class Account(CoreAccount):  # type: ignore[no-redef]  # noqa # pylint:disable=model-no-explicit-unicode
        pass


class Contact(SalesforceModel):
    # Example that db_column is not necessary for most of fields even with
    # lower case names and for ForeignKey
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING,
                                blank=True, null=True)  # db_column: 'AccountId'
    last_name = models.CharField(max_length=80)
    first_name = models.CharField(max_length=40, blank=True, null=True)
    name = models.CharField(max_length=121, sf_read_only=models.READ_ONLY,
                            verbose_name='Full Name')
    email = models.EmailField(blank=True, null=True)
    email_bounced_date = models.DateTimeField(blank=True, null=True)
    # The `default=` with lambda function is easy readable, but can be
    # problematic with migrations in the future because it is not serializable.
    # It can be replaced by normal function.
    owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                              default=models.DefaultedOnCreate(User),
                              related_name='contact_owner_set')

    def __str__(self):
        return self.name


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
    FirstName = models.CharField(max_length=40, blank=True, null=True)
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
    LeadSource = models.CharField(max_length=100,
                                  choices=[(x, x) for x in SOURCES])
    Status = models.CharField(max_length=100, choices=[(x, x) for x in STATUSES])
    Industry = models.CharField(max_length=100,
                                choices=[(x, x) for x in INDUSTRIES])
    # Added an example of special DateTime field in Salesforce that can
    # not be inserted, but can be updated
    # TODO write test for it
    EmailBouncedDate = models.DateTimeField(blank=True, null=True,
                                            sf_read_only=models.NOT_CREATEABLE)
    # Deleted object can be found only in querysets with "query_all" SF method.
    IsDeleted = models.BooleanField(default=False, sf_read_only=models.READ_ONLY)
    owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                              default=models.DefaultedOnCreate(User),
                              related_name='lead_owner_set')
    last_modified_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True,
                                         sf_read_only=models.READ_ONLY,
                                         related_name='lead_lastmodifiedby_set')
    is_converted = models.BooleanField(verbose_name='Converted',
                                       sf_read_only=models.NOT_UPDATEABLE,
                                       default=models.DEFAULTED_ON_CREATE)

    def __str__(self):
        return self.Name


class Product(SalesforceModel):
    Name = models.CharField(max_length=255)

    class Meta(SalesforceModel.Meta):
        db_table = 'Product2'

    def __str__(self):
        return self.Name


class Pricebook(SalesforceModel):
    Name = models.CharField(max_length=255)

    class Meta(SalesforceModel.Meta):
        db_table = 'Pricebook2'

    def __str__(self):
        return self.Name


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
    # the class is used only by unit tests, it is not necessary to be installed
    class Meta(SalesforceModel.Meta):
        db_table = 'ChargentOrders__ChargentOrder__c'
        custom = True
        managed = False  # can not be managed if it eventually could not exist

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


class Note(models.Model):
    title = models.CharField(max_length=80)
    body = models.TextField(null=True)
    parent_id = models.CharField(max_length=18)
    parent_type = models.CharField(max_length=50, db_column='Parent.Type', sf_read_only=models.READ_ONLY)


class Opportunity(SalesforceModel):
    name = models.CharField(max_length=255)
    contacts = django.db.models.ManyToManyField(
        Contact, through='example.OpportunityContactRole', related_name='opportunities'
    )
    close_date = models.DateField()
    stage = models.CharField(max_length=255, db_column='StageName')  # e.g. "Prospecting"
    created_date = models.DateTimeField(sf_read_only=models.READ_ONLY)
    amount = models.DecimalField(max_digits=18, decimal_places=2, blank=True, null=True)
    probability = models.DecimalField(
        max_digits=3, decimal_places=0, verbose_name='Probability (%)',
        default=models.DEFAULTED_ON_CREATE, blank=True, null=True)


class OpportunityContactRole(SalesforceModel):
    opportunity = models.ForeignKey(Opportunity, on_delete=models.DO_NOTHING, related_name='contact_roles')
    contact = models.ForeignKey(Contact, on_delete=models.DO_NOTHING, related_name='opportunity_roles')
    role = models.CharField(max_length=40, blank=True, null=True)  # e.g. "Business User"


class OpportunityLineItem(SalesforceModel):
    opportunity = models.ForeignKey(Opportunity, on_delete=models.DO_NOTHING)
    pricebook_entry = models.ForeignKey('PricebookEntry', models.DO_NOTHING, verbose_name='Price Book Entry ID',
                                        sf_read_only=models.NOT_UPDATEABLE)
    product2 = models.ForeignKey('Product', models.DO_NOTHING, verbose_name='Product ID',
                                 sf_read_only=models.NOT_UPDATEABLE)
    name = models.CharField(max_length=376, verbose_name='Opportunity Product Name', sf_read_only=models.READ_ONLY)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=18, decimal_places=2, default=models.DEFAULTED_ON_CREATE)
    unit_price = models.DecimalField(max_digits=18, decimal_places=2, verbose_name='Sales Price',
                                     default=models.DEFAULTED_ON_CREATE)


try:
    models_template = None  # type: Optional[types.ModuleType]
    from salesforce.testrunner.example import models_template
except ImportError:
    # this is useful for the case that the model is being rewritten by inspectdb
    models_template = None


class Organization(models.Model):
    name = models.CharField(max_length=80, sf_read_only=models.NOT_CREATEABLE)
    division = models.CharField(max_length=80, sf_read_only=models.NOT_CREATEABLE, blank=True)
    organization_type = models.CharField(max_length=40, verbose_name='Edition',
                                         sf_read_only=models.READ_ONLY
                                         )  # e.g 'Developer Edition', Enteprise, Unlimited...
    instance_name = models.CharField(max_length=5, sf_read_only=models.READ_ONLY, blank=True)
    is_sandbox = models.BooleanField(sf_read_only=models.READ_ONLY)
    # Fields created_by, last_modified_by, last_modified_date are dynamic

    class Meta:
        db_table = 'Organization'
        # Copy all fields that match the patters for Force.com field name
        # from the class that use the same db_table "Organization" in the
        # module models_template
        if models_template:
            dynamic_field_patterns = models_template, ['created_by', 'last.*_by']


class Test(SalesforceParentModel):
    """
    Simple custom model with one custom and more standard fields.

    Salesforce object for this model can be created:
    A) automatically from the branch hynekcer/tooling-api-and-metadata
       by commands:
        $ python manage.py shell
            >> from salesforce.backend import tooling
            >> tooling.install_metadata_service()
            >> tooling.create_demo_test_object()
    or
    B) manually can create the same object with `API Name`: `django_Test__c`
        `Data Type` of the Record Name: `Text`

       Create three fields:
       Type            | API Name | Label
       ----------------+----------+----------
       Text            | TestText | Test Text
       Checkbox        | TestBool | Test Bool
       Lookup(Contact) | Contact  | Contact

       Set it accessible by you. (`Set Field-Leved Security`)
    """
    # This is a custom field because it is defined in the custom model.
    # The API name is therefore 'TestField__c'
    test_text = models.CharField(max_length=40)
    test_bool = models.BooleanField(default=False)
    contact = models.ForeignKey(Contact, null=True, on_delete=models.DO_NOTHING)

    class Meta:
        custom = True
        db_table = 'django_Test__c'


# example of relationship from builtin object to custom object

class Attachment(models.Model):
    # A standard SFDC object that can have a relationship to any custom object
    name = models.CharField(max_length=80)
    parent = models.ForeignKey(Test, sf_read_only=models.NOT_UPDATEABLE, on_delete=models.DO_NOTHING)
    # The "body" of Attachment can't be queried for more rows togehter.
    body = models.TextField()


class Task(models.Model):
    # Reference to tables [Contact, Lead]
    who = models.ForeignKey(Lead, on_delete=models.DO_NOTHING, blank=True, null=True)
    # Refer
    what = models.ForeignKey(Account, related_name='task_what_set', on_delete=models.DO_NOTHING, blank=True, null=True)


# OneToOneField

class ApexEmailNotification(models.Model):
    """Stores who should be notified when unhandled Apex exceptions occur.

    The target can be more Salesforce users or an external email addresses.
    Available in API version 35.0 and later.
    """
    # A semicolon-delimited list of email addresses to notify when unhandled Apex exceptions occur.
    user = models.OneToOneField('User', related_name='apex_email_notification',
                                on_delete=models.DO_NOTHING, blank=True, null=True)
    # Users of your org to notify when unhandled Apex exceptions occur.
    email = models.CharField(unique=True, max_length=255, verbose_name='email', blank=True)


class Campaign(models.Model):
    name = models.CharField(max_length=80)
    number_sent = models.DecimalField(max_digits=18, decimal_places=0, verbose_name='Num Sent', blank=True, null=True)


# -------------------------------------------------------------------------------------------------------------------- #
# Patient Connections Platform Object Models
# -------------------------------------------------------------------------------------------------------------------- #

class Program(SalesforceModel):
    """
    This is the core object for operating a Customer Support Program. Re CSP is built around programs
    """
    name = models.CharField(max_length=121, db_column='Name', blank=True, null=True)
    status = models.CharField(max_length=121, db_column='DTPC_Status__c', blank=True, null=True)
    class Meta:
        custom = True
        db_table = 'DTPC_Program__c'


class InsurancePlan(SalesforceModel):
    """
    Taking the coverage record and remodeling it to an appropriate web-design
    """
    name = models.CharField(max_length=121, db_column='Name', blank=True, null=True)
    record_type_id = models.CharField(max_length=121, db_column='RecordTypeId', blank=True, null=True)
    class Meta:
        custom = True
        db_table = 'DTPC_Coverage_BI__c'


class Document(SalesforceModel):
    """
    Documents are the source of all new information within the PCP. I am going to try and 
    evaluate SP Portal documents by parsing them into a unique model.

    I'm adding in all of the fields for modeling purposes. We need to start making uique views,
    the first view will be the SP Portal documents.
    
    I'll need to load test data... I've created a few files for informatica testing
    """
    # --------------------------
    # descriptive fields
    # --------------------------

    name = models.CharField(max_length=121, db_column='Name', blank=True, null=True)
    status = models.CharField(max_length=121, db_column='Fax_Status__c')
    status_reason = models.CharField(max_length=121, db_column='DTPC_Status_Reason__c')
    affiliate = models.CharField(max_length=121, db_column='Affiliates__c')
    brand_programs = models.CharField(max_length=121, db_column='DTPC_Brand_Programs__c')
    sub_program = models.CharField(max_length=121, db_column='DTPC_PatientOne_Brand__c')
    generic_drug = models.CharField(max_length=121, db_column='DTPC_Generic_Drug_Name__c')
    record_type_id = models.CharField(max_length=121, db_column='RecordTypeId')
    category = models.CharField(max_length=121, db_column='Fax_Category__c')
    description = models.TextField(max_length=255, db_column='Description__c')
    
    # I know this is a lookup and I still need to figure out how to model the lookup fields in django
    registration = models.CharField(max_length=121, db_column='Smartform_Registration__c')

    # this is the view field that links us to a registration...
    fax_action = models.CharField(max_length=121, db_column='Fax_Action__c')

    # some docs will be attached to communication histories
    communication_history = models.CharField(max_length=121, db_column='DTPC_CommunicationHistory__c')
    attachment_id = models.CharField(max_length=25, db_column='Attachment_Id__c')


    # --------------------------
    # system info
    # --------------------------
    
    parent_document = models.CharField(max_length=121, db_column='Parent_Document__c')
    any_information_identified = models.BooleanField(db_column='isPIIIdentified__c')
    owner_full_name = models.CharField(max_length=121, db_column='DTPC_Owner_Full_Name__c')
    test_duplicate = models.CharField(max_length=121, db_column='DTPC_Test_Duplicate_Record__c')
    delete_record = models.CharField(max_length=25, db_column='DTPC_Delete_Record__c')
    archived_by = models.CharField(max_length=121, db_column='Archived_By__c')
    archived_on = models.DateTimeField(db_column='Archived_On__c')
    
    
    # --------------------------
    # faxing
    # --------------------------
    
    generate_conga = models.BooleanField(db_column='Generate_Conga__c')
    conga_parameters = models.TextField(max_length=1000, db_column='Conga_Parameters__c')
    conga_test_text = models.TextField(max_length=255, db_column='Conga_Test_Txt__c')
    conga_workflow_test = models.CharField(max_length=121, db_column='Conga_Workflow_Test__c')
    
    fax_received = models.DateTimeField(db_column='Inbound_Fax_Date_Time__c')
    fax_sent = models.DateTimeField(db_column='Fax_Sent_Date_Time__c')
    
    from_fax_number = models.CharField(max_length=255, db_column='From_Fax_Number__c')
    from_name = models.CharField(max_length=255, db_column='From_Name__c')
    
    inbound_fax = models.BooleanField(db_column='Inbound_Fax__c')
    inbound_fax_handle = models.CharField(max_length=10, db_column='Fax_Handle__c')
    inbound_fax_status = models.CharField(max_length=121, db_column='DTPC_Inbound_Fax_Status__c')
    
    isOutbound = models.BooleanField(db_column='Is_Outbound__c')
    outbound_fax_handle = models.CharField(max_length=255, db_column='Outbound_Fax_Handle__c')

    to_fax_number = models.CharField(max_length=255, db_column='To_Fax_Number__c')
    to_fax_name = models.CharField(max_length=255, db_column='To_Fax_Name__c')
    z_paper_unique_id = models.CharField(max_length=50, db_column='DTPC_zPaper_Fax_Unique_Id__c')


    # --------------------------
    # copay automation
    # --------------------------
    
    document_number = models.CharField(max_length=121, db_column='Document_Number_Formula__c')
    document_signed = models.BooleanField(db_column='DTPC_DocuSign_Document_Signed__c')
    document_type = models.CharField(max_length=121, db_column='DTPC_Document_Type__c')
    duplicate_reason = models.CharField(max_length=255, db_column='DTPC_Duplicate_Reason__c')
    
    eletter_type = models.CharField(max_length=121, db_column='DTPC_eLetter_Type__c')
    error = models.TextField(max_length=32768, db_column='Error__c')
    failure_count = models.IntegerField(db_column='Failure_Count__c')
    
    
    # --------------------------
    # hibbert
    # --------------------------

    hibbert_list_view_time_filter = models.IntegerField(db_column='DTPC_Hibbert_List_View_Time_Filter__c')
    

    # --------------------------
    # legacy fields
    # --------------------------
    
    legacy_ec_alert_id = models.CharField(max_length=80, db_column='Legacy_EC_AlertID__c')
    legacy_ec_doc_id = models.CharField(max_length=100, db_column='Legacy_EC_DocID__c')
    legacy_ec_ifa_id = models.CharField(max_length=80, db_column='Legacy_EC_IFAID__c')
    legacy_eg_fax_id = models.CharField(max_length=80, db_column='Legacy_EG_FaxID__c')
    legacy_system_patient_id = models.CharField(max_length=50, db_column='Legacy_System_Patient_ID__c')
    

    # --------------------------
    # mark ups...
    # --------------------------

    marked_spam_by = models.CharField(max_length=121, db_column='Marked_Spam_By__c')
    marked_spam_on = models.DateField(db_column='Marked_Spam_On__c')
    mark_for_delete = models.BooleanField(db_column='Mark_for_Delete__c')
    

    # found deprecatations
    # --------------------------
    # fax_unique_id = models.CharField(max_length=50, db_column='Fax_Unique_Id__c')
    # isMasked = models.BooleanField(db_column='DTPC_isMasked__c')
    # legacy_system_document_id = models.CharField(max_length=50, db_column='Legacy_System_Document_ID__c')
    # legacy_system_source = models.CharField(max_length=50, db_column='Legacy_System_Source__c')
    # legacy_system_source = models.CharField(max_length=50, db_column='Legacy_System_Source__c')
    # record_shared = models.BooleanField(db_column='DTPC_Record_Shared__c')
    # related_records_id = models.TextField(max_length=131072, db_column='DTPC_Related_Record_Ids__c')
    # reviewed = models.CharField(max_length=121, db_column='DTPC_Reviewed__c')
    # share_on_hcp_portal = models.BooleanField(db_column='DTPC_Share_on_HCP_Portal__c')
    # sms_body = models.TextField(max_length=32768, db_column='DTPC_SMS_Body__c')
    # sms_phone_number = PhoneField(blank=True, help_text='sms phone number', db_column='DTPC_SMS_Phone_Number__c')
    # sms_timestamp = models.DateTimeField(db_column='DTPC_SMS_timestamp__c')

    class Meta:
        custom = True
        db_table = 'DTPC_Document__c'
