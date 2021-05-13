"""
Data modeler for the Salesforce Platform 

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
    

    # fields in setup, cannot be found in query
    # ------------------------------------------------
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


class Registration(SalesforceModel):
    """
    Registration model

    """

    # --------------------------
    # system information
    # --------------------------

    name = models.CharField(max_length=121, db_column='Name', blank=True, null=True)
    registration_type = models.CharField(max_length=121, db_column='Registration_Type__c')

    hub_patient_id = models.CharField(max_length=255, db_column='Hub_Patient_ID__c')
    
    affiliate = models.CharField(max_length=121, db_column='DTPC_Affiliate__c')
    brand_program_picklist = models.CharField(max_length=121, db_column='DTPC_Brand_Program_Picklist__c')
    generic_drug_name = models.CharField(max_length=121, db_column='DTPC_Generic_Drug_Name__c')

    mmn_number = models.CharField(max_length=30, db_column='DTPC_MMN_Number__c')

    fax = models.CharField(max_length=20, db_column='Fax__c')

    added_hub_patient_id = models.CharField(max_length=255, db_column='Added_Hub_Patient_ID__c')
    date_action_recorded = models.DateField(db_column='Date_Action_Recorded__c')

    products = models.CharField(max_length=121, db_column='DTPC_Products__c')
    reviewed_manually = models.BooleanField(db_column='DTPC_Reviewed_Manually__c')
    program_registration = models.CharField(max_length=121, db_column='DTPC_Program_Registration__c')

    subject = models.CharField(max_length=255, db_column='DTPC_Subject__c')
    patientone_brand = models.CharField(max_length=121, db_column='DTPC_PatientOne_Brand__c')
    
    test_duplicate_record = models.CharField(max_length=255, db_column='DTPC_Test_Duplicate_Record__c')

    sent_from = models.CharField(max_length=255, db_column='DTPC_Sent_From__c')
    sent_to = models.CharField(max_length=255, db_column='DTPC_Sent_To__c')


    # --------------------------
    # patient demographics
    # --------------------------
    
    first_name = models.CharField(max_length=255, db_column='DTPC_First_Name__c')
    last_name = models.CharField(max_length=255, db_column='DTPC_Last_Name__c')
    middle_name = models.CharField(max_length=255, db_column='DTPC_Middle_Name__c')
    eighteen_years_of_age = models.BooleanField(db_column='DTPC_18_years_of_Age__c')
    gender = models.CharField(max_length=121, db_column='Gender__c')
    address = models.CharField(max_length=255, db_column='Address__c')
    city = models.CharField(max_length=100, db_column='City__c')
    state = models.CharField(max_length=121, db_column='State__c')
    zip_code = models.CharField(max_length=32, db_column='Zip_Code__c')
    date_of_birth = models.DateField(db_column='Date_of_Birth__c')
    email = models.EmailField(db_column='Email__c')
    phone = PhoneField(db_column='Phone__c')


    patient_registration = models.CharField(max_length=121, db_column='DTPC_Patient_Registration__c')
    patient_name = models.CharField(max_length=121, db_column='Patient_Name__c')
    patient_address_registration = models.CharField(max_length=255, db_column='DTPC_Patient_Address_Registration__c')
    patient_attestation = models.BooleanField(db_column='DTPC_Patient_Attestation__c')
    patient_or_caregiver = models.CharField(max_length=121, db_column='DTPC_Patient_or_Caregiver__c')
    patient_state_of_residence = models.CharField(max_length=121, db_column='DTPC_Patient_State_of_Residence__c')

    primary_address_line_1 = models.CharField(max_length=255, db_column='DTPC_Primary_Address_Line_1__c')
    primary_address_line_2 = models.CharField(max_length=255, db_column='DTPC_Primary_Address_Line_2__c')

    primary_country = models.CharField(max_length=121, db_column='DTPC_Primary_Country__c')

    other_deignation = models.CharField(max_length=100, db_column='Other_Designation__c')
    primary_languages_spoken = models.CharField(max_length=121, db_column='Primary_Language_Spoken__c')
    other_language_spoken = models.CharField(max_length=100, db_column='Other_Language_Spoken__c')

    preferred_date_to_contact_me = models.DateField(db_column='Preferred_date_to_contact_me__c')
    preferred_phone_type = models.CharField(max_length=121, db_column='Preferred_Phone_Type__c')
    prefered_time_for_call = models.CharField(max_length=121, db_column='DTPC_Prefered_Time_for_Call__c')
    preferred_time_to_contact = models.CharField(max_length=121, db_column='Preferred_time_to_contact__c')


    # --------------------------
    # caregiver demographics
    # --------------------------

    caregiver_registration = models.CharField(max_length=121, db_column='DTPC_Caregiver_Registration__c')
    caregiver_18_years_of_age = models.BooleanField(db_column='DTPC_Caregiver_18_Years_of_Age__c')
    caregiver_address = models.CharField(max_length=255, db_column='DTPC_Caregiver_Address__c')
    caregiver_city = models.CharField(max_length=100, db_column='DTPC_Caregiver_City__c')
    caregiver_date_of_birth = models.DateField(db_column='DTPC_Caregiver_Date_of_Birth__c')	
    caregiver_email = models.EmailField(db_column='DTPC_Caregiver_Email__c')
    caregiver_first_name = models.CharField(max_length=255, db_column='DTPC_Caregiver_First_Name__c')
    caregiver_last_name = models.CharField(max_length=255, db_column='DTPC_Caregiver_Last_Name__c')
    caregiver_phone = PhoneField(db_column='DTPC_Caregiver_Phone__c')
    caregiver_state = models.CharField(max_length=121, db_column='DTPC_Caregiver_State__c')
    caregiver_zip = models.CharField(max_length=32, db_column='DTPC_Caregiver_Zip__c')


    # --------------------------
    # coverage information
    # --------------------------
    
    insurance_plan_name = models.CharField(max_length=255, db_column='DTPC_Insurance_Plan_Name__c')
    insurance_effective_date = models.DateField(db_column='Insurance_Effective_Date__c')
    insurnace_investigation = models.CharField(max_length=121, db_column='DTPC_Insurance_Investigation__c')
    insurance_type = models.CharField(max_length=121, db_column='DTPC_Insurance_Type__c')

    primary_insurance_company = models.CharField(max_length=255, db_column='DTPC_Primary_Insurance_Company__c')
    primary_insurance_company_phone = PhoneField(db_column='DTPC_Primary_Insurance_Company_Phone__c')
    primary_insurance_group_number = models.CharField(max_length=100, db_column='DTPC_Primary_Insurance_Group_Number__c')
    primary_insurance_number = models.CharField(max_length=100, db_column='DTPC_Primary_Insurance_Number__c')
    primary_insurance_policyholder = models.CharField(max_length=255, db_column='DTPC_Primary_Insurance_Policyholder__c')

    secondary_insurance_company = models.CharField(max_length=255, db_column='DTPC_Secondary_Insurance_Company__c')
    secondary_insurance_company_phone = PhoneField(db_column='DTPC_Secondary_Insurance_Company_Phone__c')
    secondary_insurance_group_number = models.CharField(max_length=100, db_column='DTPC_Secondary_Insurance_Group_Number__c')
    secondary_insurance_number = models.CharField(max_length=100, db_column='DTPC_Secondary_Insurance_Number__c')
    secondary_insurance_policyholder = models.CharField(max_length=255, db_column='DTPC_Secondary_Insurance_Policyholder__c')
    
    is_patient_insured = models.CharField(max_length=121, db_column='DTPC_Is_Patient_Insured__c')

    copay_card_number = models.CharField(max_length=50, db_column='DTPC_Copay_Card_Number__c')
    benefit_converted = models.CharField(max_length=121, db_column='Benefit_Converted__c')

    pa_denial_reason = models.CharField(max_length=255, db_column='PA_Denial_Reason__c')
    pa_expired = models.CharField(max_length=121, db_column='PA_Expired__c')
    pa_outcome = models.CharField(max_length=121, db_column='PA_Outcome__c')
    pa_submitted = models.CharField(max_length=121, db_column='PA_Submitted__c')
    pa_submitted_date = models.DateField(db_column='PA_Submitted_Date__c')

    appeal_denial_reason = models.CharField(max_length=255, db_column='Appeal_Denial_Reason__c')
    appeaal_outcome = models.CharField(max_length=121, db_column='Appeal_Outcome__c')
    appeal_submitted = models.CharField(max_length=121, db_column='Appeal_Submitted__c')
    appeal_submitted_date = models.CharField(max_length=121, db_column='Appeal_Submitted_Date__c')

    """
    These fields were supposed to be added in R24, but were not found on initial query...
    # me_denial_reason = models.CharField(max_length=255, db_column='DTPC_ME_Denial_Reason__c')
    # me_outcome = models.CharField(max_length=121, db_column='DTPC_ME_Outcome__c')
    # me_submitted = models.CharField(max_length=121, db_column='DTPC_ME_Submitted__c')
    # me_submitted_date = models.DateField(db_column='DTPC_ME_Submitted_Date__c')
    # pa_not_available = models.CharField(max_length=121, db_column='DTPC_PA_Not_Available__c')
    # mandatory_transfer = models.BooleanField(db_column='DTPC_Mandatory_Transfer__c')
    """

    household_income_cammelcase = models.DecimalField(max_digits=6, decimal_places=2, db_column='DTPC_HouseholdIncome__c')
    number_of_persons_in_household = models.IntegerField(db_column='DTPC_Number_of_Persons_in_Household__c')
    

    # --------------------------
    # services information
    # --------------------------

    signature_completed = models.BooleanField(db_column='DTPC_Signature_Completed__c')
    signature_completed_date = models.DateField(db_column='DTPC_Signature_Completed_Date__c')

    on_label = models.BooleanField(db_column='DTPC_On_Label__c')

    indication = models.CharField(max_length=121, db_column='DTPC_Indication__c')
    diagnosis_icd_10_code = models.CharField(max_length=100, db_column='DTPC_Diagnosis_ICD_10_Code__c')
    secondary_diagnosis_code = models.CharField(max_length=255, db_column='DTPC_Secondary_Diagnosis_Code__c')
    
    hippa_consent = models.BooleanField(db_column='DTPC_HIPPA_Consent__c')
    hipaa_consent_date = models.DateField(db_column='DTPC_HIPAA_Consent_Date__c')

    tcpa_consent = models.BooleanField(db_column='DTPC_TCPA_Consent__c')
    tcpa_consent_date = models.DateField(db_column='DTPC_TCPA_Consent_Date__c')

    marketing_consent = models.BooleanField(db_column='DTPC_Marketing_Consent__c')
    marketing_consent_date = models.DateField(db_column='DTPC_Marketing_Consent_Date__c')
    
    medical_research_consent = models.BooleanField(db_column='DTPC_Medical_Research_Consent__c')
    medical_research_consent_date = models.DateField(db_column='DTPC_Medical_Research_Consent_Date__c')

    csp_services = models.CharField(max_length=121, db_column='CSP_Services__c')
    
    date_enrollment_processed = models.DateField(db_column='DTPC_Date_Enrollment_Processed__c')
    
    days_to_signature = models.IntegerField(db_column='Days_to_Signature__c')
    
    designation = models.CharField(max_length=121, db_column='Designation__c')

    docusign_mkt_sms_enabled = models.BooleanField(db_column='DTPC_DocuSign_MKT_SMSEnabled__c')
        
    docusign_copay_card = models.BooleanField(db_column='DTPC_DocuSign_Co_Pay_Card__c')
    docusign_fr_support = models.BooleanField(db_column='DTPC_DocuSign_FR_Support__c')
    docusign_insurance_investigation = models.BooleanField(db_column='DTPC_DocuSign_Insurance_Investigation__c')
    docusign_ongoing_support = models.BooleanField(db_column='DTPC_DocuSign_Ongoing_Support__c')
    
    do_not_sell = models.BooleanField(db_column='DTPC_Do_Not_Sell__c')
    
    email_consent = models.BooleanField(db_column='DTPC_Email_Consent__c')
    email_consent_date = models.DateField(db_column='DTPC_Email_Consent_Date__c')
    
    e_sign_act_acceptance_date = models.CharField(max_length=50, db_column='E_SIGN_Act_Acceptance_Date__c')
    
    fr_support_insurance_investigation = models.BooleanField(db_column='DTPC_FR_Support_Insurance_Investigation__c')
    
    injection_training = models.CharField(max_length=121, db_column='DTPC_Injection_Training__c')
    sharps_disposal = models.CharField(max_length=255, db_column='DTPC_Sharps_Disposal__c')

    ongoing_support = models.CharField(max_length=121, db_column='DTPC_Ongoing_Support__c')

    additional_services_backend = models.BooleanField(db_column='DTPC_Additional_Services_backend__c')
    additional_services_consent = models.BooleanField(db_column='DTPC_Additional_Services_Consent__c')
    additional_services_consent_date = models.DateField(db_column='DTPC_Additional_Services_Consent_Date__c')

    text_consent = models.BooleanField(db_column='DTPC_Text_Consent__c')
    text_message_reminders = models.CharField(max_length=255, db_column='Text_message_reminders__c')
    
    treatent_reminders = models.CharField(max_length=255, db_column='DTPC_Treatment_Reminders__c')
    treatment_setting = models.CharField(max_length=255, db_column='DTPC_Treatment_Setting__c')
    treatment_start_date = models.DateField(db_column='DTPC_Treatment_Start_Date__c')	
    
    verification_method = models.CharField(max_length=50, db_column='DTPC_Verification_Method__c')

    ordered_specialty_pharmacy_directly = models.CharField(max_length=121, db_column='DTPC_Ordered_specialty_pharmacy_directly__c')
    

    # --------------------------
    # hcp information
    # --------------------------

    facility_name = models.CharField(max_length=100, db_column='Facility_Name__c')
    hospital_address = models.CharField(max_length=255, db_column='DTPC_Hospital_Address__c')
    hospital_name = models.CharField(max_length=255, db_column='DTPC_Hospital_Name__c')
    hospital_npi = models.CharField(max_length=100, db_column='DTPC_Hospital_NPI__c')
    hospital_tax_id = models.CharField(max_length=100, db_column='DTPC_Hospital_Tax_ID__c')
    npi = models.CharField(max_length=20, db_column='NPI__c')
    
    office_contact_name = models.CharField(max_length=20, db_column='Office_Contact_Name__c')
    office_contact_phone = PhoneField(db_column='DTPC_Office_Contact_Phone__c')

    physician_medicaid = models.CharField(max_length=100, db_column='DTPC_Physician_Medicaid_ID__c')
    physician_tax_id = models.CharField(max_length=100, db_column='DTPC_Physician_Tax_ID__c')
    
    prescriber_address = models.CharField(max_length=255, db_column='DTPC_Prescriber_Address__c')
    prescriber_address_2 = models.CharField(max_length=255, db_column='Prescriber_Address_2__c')
    prescriber_city = models.CharField(max_length=100, db_column='DTPC_Prescriber_City__c')
    prescriber_fax = models.CharField(max_length=20, db_column='DTPC_Prescriber_Fax__c')
    prescriber_first_name = models.CharField(max_length=255, db_column='DTPC_Prescriber_First_Name__c')
    prescriber_last_name = models.CharField(max_length=255, db_column='DTPC_Prescriber_Last_Name__c')
    prescriber_middle_name = models.CharField(max_length=255, db_column='Prescriber_Middle_Name__c')
    prescriber_name = models.CharField(max_length=255, db_column='Prescriber_Name__c')
    prescriber_phone = PhoneField(db_column='DTPC_Prescriber_Phone__c')
    prescriber_practice_name = models.CharField(max_length=255, db_column='DTPC_Prescriber_Practice_Name__c')
    prescriber_state = models.CharField(max_length=121, db_column='DTPC_Prescriber_State__c')
    prescriber_zip = models.CharField(max_length=32, db_column='Prescriber_Zip__c')

    ras_results = models.CharField(max_length=100, db_column='DTPC_RAS_Results__c')


    # --------------------------
    # pharmacy information
    # --------------------------

    pharmacy_name = models.CharField(max_length=255, db_column='Pharmacy_Name__c')
    ncpdp = models.CharField(max_length=255, db_column='NCPDP__c')
    
    docusign_rxbin = models.CharField(max_length=50, db_column='DTPC_DocuSign_RxBIN__c')
    docusign_rxgroup = models.CharField(max_length=100, db_column='DTPC_DocuSign_RxGroup__c')
    docusign_rxpcn = models.CharField(max_length=50, db_column='DTPC_DocuSign_RxPCN__c')
    

    # fields in setup, cannot be found in query
    # ------------------------------------------------
    # additional_notes = models.CharField(max_length=255, db_column='DTPC_Additional_Notes__c')
    # associated_brand_programs = models.CharField(max_length=121, db_column='Associated_Brand_Programs__c')
    # automation_indicator = models.BooleanField(db_column='DTPC_Automation_Indicator__c')
    # brnd_site_identifier = models.BooleanField(db_column='DTPC_Brand_Site_Identifier__c')
    # brand_site_url = models.CharField(max_length=100, db_column='DTPC_Brand_Site_Url__c')
    # buildings = models.CharField(max_length=255, db_column='Buildings__c')
    # caregiver_phone_number_type = models.CharField(max_length=255, db_column='DTPC_Caregiver_Phone_Number_Type__c')
    # date_of_birth_docusign = models.CharField(max_length=50, db_column='DTPC_Date_of_Birth_Docusign__c')
    # delete_record = models.CharField(max_length=121, db_column='DTPC_Delete_Record__c')
    # docusign_injection_training = models.BooleanField(db_column='DTPC_DocuSign_Injection_Training__c')
    # docusign_sharps = models.BooleanField(db_column='DTPC_DocuSign_Sharps__c')
    # dr_code = models.CharField(max_length=255, db_column='DTPC_Dr_Code__c')
    # docusign_envelope_id = models.CharField(max_length=100, db_column='DTPC_DocuSign_Envelope_ID__c')
    # docusign_envelope_status = models.CharField(max_length=100, db_column='DTPC_Docusign_Envelope_Status__c')
    # e_sign_metadata = models.TextField(max_length=32768, db_column='DTPC_E_Sign_Metadata__c')
    # first_name_furigana = models.CharField(max_length=255, db_column='DTPC_First_Name_Furigana__c')
    # furigana = models.CharField(max_length=255, db_column='DTPC_Furigana__c')
    # hcp_name_furigana = models.CharField(max_length=255, db_column='DTPC_HCP_name_Furigana__c')
    # household_income = models.CharField(max_length=255, db_column='DTPC_Household_Income__c')
    # interests = models.CharField(max_length=121, db_column='DTPC_Interests__c')
    # last_name_furigana = models.CharField(max_length=255, db_column='DTPC_Last_Name_Furigana__c')
    # uid = models.CharField(max_length=255, db_column='DTPC_UID__c')
    # magazine_serive = models.CharField(max_length=121, db_column='DTPC_Magazine_Service__c')
    # magazine_service_type = models.CharField(max_length=121, db_column='DTPC_Magazine_Service_Type__c')
    # mail_consent = models.CharField(max_length=6, db_column='DTPC_Mail_Consent__c')
    # mail_consent_date = models.DateField(db_column='DTPC_Mail_Consent_Date__c')
    # national_identification_number = models.CharField(max_length=100, db_column='DTPC_National_Identifcation_Number__c')
    # opt_out = models.BooleanField(db_column='DTPC_Opt_Out__c')
    # participant = models.CharField(max_length=121, db_column='Participant__c')
    # patient = models.CharField(max_length=121, db_column='DTPC_Patient__c')
    # permission_to_send_sms = models.CharField(max_length=121, db_column='DTPC_Permission_to_send_SMS__c')
    # phone_number_2 = PhoneField(db_column='DTPC_Phone_Number_2__c')
    # phone_number_3 = PhoneField(db_column='DTPC_Phone_Number_3__c')
    # phone_number_type = models.CharField(max_length=255, db_column='DTPC_Phone_Number_Type__c')
    # prefered_date_for_first_call_1 = models.DateField(db_column='DTPC_Prefered_Date_for_First_Call_1__c')
    # prefered_date_for_first_call_2 = models.DateField(db_column='DTPC_Prefered_Date_for_First_Call_2__c')
    # preferred_day_of_call = models.CharField(max_length=121, db_column='DTPC_Preferred_Day_of_Call__c')
    # preferred_length_of_call = models.CharField(max_length=121, db_column='DTPC_Preferred_Length_of_Call__c')
    # preferred_telephone_number = models.CharField(max_length=121, db_column='DTPC_Preferred_Telephone_Number__c')
    # primary_address_line_3 = models.CharField(max_length=255, db_column='DTPC_Primary_Address_Line_3__c')
    # primary_insurance_owner_type = models.CharField(max_length=121, db_column='DTPC_Primary_Insurance_Owner_Type__c')
    # primary_insurance_policyholder_dob = models.DateField(db_column='DTPC_Primary_Insurance_Policyholder_DOB__c')
    # primary_prefecture = models.CharField(max_length=255, db_column='DTPC_Primary_Prefecture__c')
    # program = models.CharField(max_length=121, db_column='DTPC_Program__c')
    # province = models.CharField(max_length=255, db_column='DTPC_Province__c')
    # record_shared = models.BooleanField(db_column='DTPC_Record_Shared__c')
    # registration_status = models.CharField(max_length=255, db_column='DTPC_Registration_Status__c')
    # related_record_ids = models.TextField(max_length=131072, db_column='DTPC_Related_Record_Ids__c')
    # relationship_to_patient = models.CharField(max_length=255, db_column='DTPC_Relationship_To_Patient__c')
    # requester_email_address = models.EmailField(db_column='DTPC_Requester_e_mail_address__c')
    # requester_name = models.CharField(max_length=255, db_column='DTPC_Requester_name__c')
    # reviewed = models.CharField(max_length=121, db_column='DTPC_Reviewed__c')
    # salutation = models.CharField(max_length=121, db_column='DTPC_Salutation__c')
    # secondary_insurance_owner_type = models.CharField(max_length=121, db_column='DTPC_Secondary_Insurance_Owner_Type__c')
    # secondary_insurance_policyholder_dob = models.DateField(db_column='DTPC_Secondary_Insur_Policyholder_DOB__c')
    # services_requested = models.CharField(max_length=255, db_column='DTPC_Services_Requested__c')
    # share_information_with_doctor = models.CharField(max_length=255, db_column='DTPC_Share_information_with_Doctor__c')
    # sms_consent_date = models.DateField(db_column='DTPC_SMS_Consent_Date__c')
    # sms_language = models.CharField(max_length=10, db_column='DTPC_SMS_Language__c')
    # street = models.CharField(max_length=255, db_column='DTPC_Street__c')
    # reg_json = models.TextField(max_length=32768, db_column='DTPC_Reg_JSON__c')
    # surveys = models.CharField(max_length=255, db_column='DTPC_Surveys__c')

    class Meta:
        custom = True
        db_table = 'DTPC_Registration__c'


class SPStautsUpdate(SalesforceModel):
    """
    New object for the SP Status updates
    """

    # --------------------------
    # update fields from the sp
    # --------------------------
    added_hub_patient_id = models.CharField(max_length=255, db_column='Added_HUB_Patient_ID__c')
    appeal_denial_reason = models.CharField(max_length=255, db_column='Appeal_Denial_Reason__c')
    appeal_status = models.CharField(max_length=255, db_column='Appeal_Status__c')
    appeal_submitted = models.CharField(max_length=255, db_column='Appeal_Submitted__c')
    appeal_submitted_date = models.DateTimeField(db_column='Appeal_Submitted_Date__c')
    benefit_converted = models.CharField(max_length=255, db_column='Benefit_Converted__c')
    brand_program = models.CharField(max_length=255, db_column='Brand_Program__c')
    date_action_recorded = models.DateTimeField(db_column='Date_Action_Recorded__c')
    group_number = models.CharField(max_length=11, db_column='Group_Number__c')
    hcp_address_1 = models.CharField(max_length=25, db_column='HCP_Address_1__c')
    hcp_address_2 = models.CharField(max_length=35, db_column='HCP_Address_2__c')
    hcp_city = models.CharField(max_length=20, db_column='HCP_City__c')
    hcp_first_name = models.CharField(max_length=25, db_column='HCP_First_Name__c')
    hcp_last_name = models.CharField(max_length=25, db_column='HCP_Last_Name__c')
    hcp_phone = PhoneField(db_column='HCP_Phone__c')
    hcp_state = models.CharField(max_length=2, db_column='HCP_State__c')
    hcp_zip = models.CharField(max_length=5, db_column='HCP_Zip__c')
    hub_patient_id = models.CharField(max_length=12, db_column='Hub_Patient_ID__c')
    insurance_bin = models.CharField(max_length=8, db_column='Insurance_BIN__c')
    insurance_group = models.CharField(max_length=15, db_column='Insurance_Group__c')
    insurance_id = models.CharField(max_length=25, db_column='Insurance_ID__c')
    insurance_pcn = models.CharField(max_length=10, db_column='Insurance_PCN__c')
    insurance_phone = PhoneField(db_column='Insurance_Phone__c')
    iqvia_bin = models.CharField(max_length=6, db_column='IQVIA_BIN__c')
    iqvia_pcn = models.CharField(max_length=10, db_column='IQVIA_PCN__c')
    me_denial_reason = models.CharField(max_length=255, db_column='ME_Denial_Reason__c')
    medical_exception = models.CharField(max_length=255, db_column='Medical_Exception__c')
    me_status = models.CharField(max_length=255, db_column='ME_Status__c')
    me_submitted_date = models.DateTimeField(db_column='ME_Submitted_Date__c')
    ncpdp = models.CharField(max_length=7, db_column='NCPDP__c')
    npi_dea = models.CharField(max_length=10, db_column='NPI_DEA__c')
    on_label = models.BooleanField(db_column='On_Label__c')
    pa_fe_submitted = models.CharField(max_length=255, db_column='PA_FE_Submitted__c')
    pa_fe_denial_reason = models.CharField(max_length=255, db_column='PA_FE_Denial_Reason__c')
    pa_fe_status = models.CharField(max_length=255, db_column='PA_FE_Status__c')
    pa_fe_submitted_date = models.DateTimeField(db_column='PA_FE_Submitted_Date__c')
    pa_na_submitted_date = models.DateTimeField(db_column='PA_N_A_Submitted_Date__c')
    payer_name = models.CharField(max_length=255, db_column='Payer_Name__c')
    pharmacy_name = models.CharField(max_length=255, db_column='Pharmacy_Name__c')
    plan_name = models.CharField(max_length=255, db_column='Plan_Name__c')
    prior_authorization_na = models.CharField(max_length=255, db_column='Prior_Authorization_N_A__c')
    savings_card_id = models.CharField(max_length=12, db_column='Savings_Card_ID__c')
    transfer = models.BooleanField(db_column='Transfer__c')

    class Meta:
        custom = True
        db_table = 'SP_Status_Update__c'