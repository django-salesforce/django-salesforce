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

Example:

.. code:: python

    class Contact(SalesforceModel):
        # we add a custom field "my_field" to a standard object "Contact"
        last_name = models.CharField(max_length=50)
        my_field = models.CharField(max_length=50, null=True, sf_managed=True)

    class MyObject(SalesforceModel):
        # a field with API name "Name" is created automatically by SFDC. "max_length" is ignored.
        name = models.CharField(max_length=50, verbose_name="My Object Name")
        my_field = models.CharField(max_length=50, null=True)  # this is a custom field and it is sf_managed

        Meta:
            sf_managed = True
            # db_table = MyObject__c

    class OtherObject2(SalesforceModel):
        # we prefer an automatic read only name here in style "A-{0000}" here
        name = models.CharField(max_length=50, sf_read_only=models.READ_ONLY)
        ...

        Meta:
            sf_managed = True
            # db_table = OtherObject2__c


.. code:: shell

    $ python manage.py makemigrations
    $ python manage.py migrate --database=salesforce

Custom fields in objects managed by Django are also managed by Django by default,
but it is possible to set a parameter ``sf_managed=False`` to disable it.

If you want to start to manage a field that has been created manually then also read and edit
permissions for that field must be enabled in "Django_Salesforce" permission set even if the field
is accessible also by a user profile.


Troubleshooting
---------------

Migrations are excellent in develomment especially if they are used since the beginning.
They can be problematic if management by Django has been combined with some manual administration of the same objects.

An interactive option ``--ask`` is implemented that allows to interactively skip
any individual part of migration if it failed because a duplicit object is created
or an object is deleted, but it has been deleted previously.
It allows also to ignore an error interactively or raise or to start debugging
if the printed error message wad pythons be insufficient.

.. code::

    $ python manage.py migrate --ask --database=salesforce ...

    Running migrations:
        Applying example.0001_initial...
    create_model(<model Test>)
    Run this command [Y/n]: n


Unimplemented features - caveats
--------------------------------

(The implementation is kept simple until usefulness of migrations will be appreciated enough,)

All migration operations are currently implemented without transactions and without
any optimization. Every field is processed by an individual command.


All deleted objects and fields remain in a trash bin and they are not purged on delete.
