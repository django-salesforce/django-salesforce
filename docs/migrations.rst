Migrations
==========

new in 3.2.1

Django-Salesforce can create custom objects and custom fields in a Salesforce (SFDC) database by
``migrate`` command.
A general practice in Saleforce is that more packages from more vendors are installed and not
all custom objects and fields should be managed by Django. Therefore the management by Django
must be explicitly enabled in the Django model and also in Salesforce administration to prevent
a mistake that a database is managed unitentionally.

If and only if you want to run migrations on a Salesforce database then create a permission set
with the API name ``Django_Salesforce``. Assign that permission set also to the current user
to can access data in new object types that will be created by Django.

Custom object in Salesforce that should be created and managed by Django must be marked by Meta: ``sf_managed = True``.
Custom fields can be created also in standard objects or in other objects not managed
by Django if a field is marked by a parameter ``sf_managed=True``.

Example:_

    class MyObject(SalesforceModel):
        name = models.CharField(max_length=50)  # a field e.g. with API name "Name" is created automatically by SFDC
        my_field = models.CharField(max_length=50, null=True)  # this is a custom field and sf_managed

        Meta:
            sf_managed = True
            # db_table = MyObject__c

    class Contact(SalesforceModel):
        last_name = models.CharField(max_length=50)
        my_field = models.CharField(max_length=50, null=True, sf_managed=True)

        Meta:
            # db_table = MyObject__c


Custom fields in objects managed by Django are also managed by Django by default,
but it is possible to set a parameter ``sf_managed=False`` to disable it.

If you want to start to manage a field that has been created manually then also read and edit
permissions for that field must be enabled in "Django_Salesforce" permission set evan if the field
is accessible by a user profile yet.


Unimplemented features - caveats
--------------------------------

(The implementation is keep simple until usefulness of migrations will be appreciated,
e.g. by sponsorship.)

All migration operations are currently implemented without transactions and without
any optimization. Every field is processed by an individual command.

Migrations can be excellent in develomment especially if they have been used since the beging,
but they can be problematic if a management by Django is combined in the same application
with manual administration.

No interactive feature "migrate" command is currenly implemented, although it could
be very useful in future e.g. to select continue or quit after an error e.g. if the field exists yet.

All deleted objects and fields remain in a trash bin and they are not purged on delete.
