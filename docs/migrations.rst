Migrations
==========

new in v3.2.1.

Migrations command ``migrate`` is supported in SFDC.

Django-Salesforce can create custom objects and custom fields in a Salesforce database (SFDC) by
``migrate`` command. A general practice with Saleforce is that more packages from more vendors
are installed in the organization and not
all custom objects and fields should be managed by Django. Therefore the management by Django
modifies SFDC only if it is explicitly enabled in the Django model and also in Salesforce administration,
to prevent a mistake that some part of the database is managed unitentionally.

Another security feature is that all destructive operations ``delete_model`` and ``remove_fieldgare``
are interactive on production databases and every delete must be confirmed.

If and only if you want to run migrations on a Salesforce database then:

| 1) Create a permission set with the API name ``Django_Salesforce``.  
|    ``python manage.py migrate --database=salesforce --create-permission-set``  
|    That only creates the permission set and the table "django_migrations" (label "migrations"), without running any migration.  
| 2) Assign that permission set also to the current user to can access data in new object types that will be created by Django.
| 3) Custom object in Salesforce that should be created and managed by Django must be marked by Meta: ``sf_managed = True``.
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

Objects and fields created by Django are enabled in Django_Salesforce permission set and can be
also modified and deleted by Django. If an existing sf_managed object is not enabled
in the pemission set then it is skipped with a warning and its settings can not be modified.

If you want to start to manage an object that has been created manually then enable all
Object Permissions for that object in "Django_Salesforce" permission set even if the field
is accessible still by user profiles.

| **Terminology**:  
| **Model** in Django terminology is an equivalent of **Table** in database terminology and
an equivalent of **Object** in Salesforce terminology. These three points af vew are used in this text.  
|
| **Builtin** object and builtin field  have a name without any double underscore ``'__'``.  
| **Custom** object and custom field ore in the form ``ApiName__c`` with only a suffix ``__c``
and without any other double underscore.  
| **Namespace** object and namespace field are in the form ``NameSpace__ApiName__c``.
|  
|  
| Because custom fields can be managed by Django automatically in SFDC then their db_column
is not too important if the algorithm is guaranted stable.
If no **db_column** is specified then it can be derived from "django field name" this way:
| If the django field name is not lower case then the default api name is the same.
| Default API name from a lower case name is created by capitalizing and removing spaces:  
| e.g. default api name "LastModifiedDate" can be created from "last_modified_date" or from
"LastModifiedDate".
| Custom field can be rocognized by "custom=True".
| Namespace field can be recognized by "sf_prefix='NameSpacePrefix'".
| All unspecified fields without "db_column" in custom objects are expected custom field,
except a few standard well known system names like "LastModifiedDate".  
|
| If you find a new not recognized system name then report it as a bug and specify
an explicit "custom=False" or an explicit "db_column=...", but it is extremely unprobable
because I verify all system names in a new API before I enable that API version in a new
version of django-salesforce.


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

All fields that can be managed by Django in SFDC are identified in ``migrations/*.py``
exactly by an explicit parameter ``sf_managed=True``.
In ``models.py`` can be the right value ``field.sf_managed`` usually recognized from a simplified model:

- Custom fields in sf_managed custom object are sf_managed by default.
- Custom fields in non sf_managed objects are not sf_managed by default.
- Builtin fields and namespace fields, builtin objects and namespace objects should be never sf_managed.
- The "Name" field (a field with db_column='Name') is a special part of a database Object and
  its sf_managed values is not important. Its sf_managed should be omitted or the same as the value
  of the object.

My useful answer how to use e.g. an option
``**migrate --fake** at Stackoverflow <https://stackoverflow.com/a/46774336/448474>``__.

Unimplemented features - caveats
--------------------------------

The implementation is kept simple until usefulness of migrations will be appreciated enough.

All migration operations are currently implemented without transactions and without
any optimization. Every field is processed by an individual command.

It is not possible to detect only a change of model Meta options ``verbose_name`` or ``verbose_name_plural``.
You should change change also someting unimportant in the ``Name`` field of that model
in the same transaction e.g. change the unused ``max_length`` parameter or add a space
at the end of ``verbose_name`` of Name field. That will trigger update of metadata of
the CustomObject in Salesforce.

There is a risk that a field can not be created becase e.g. a duplicit related name exist in trash bin
and also that a field can not be deleted because it is used by something important in Salesforce.
That are usual problems also with manual administrations, but that could cause an uncosistent migration,
because a transaction is not currently used. There if you want to use migrations in production,
verify debug it on a sandbox, then create a fresh sandbox from production and verify the migration again.

Master-Detail Relationship is not currently implemented even that it is an important type.

All deleted objects and fields remain in a trash bin and they are not purged on delete.
