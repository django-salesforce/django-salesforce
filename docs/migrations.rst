Migrations
==========

new in v3.2.1.

Migrations are now supported in Salesforce databases also on SFDC site.
The command ``python manage.py migrate --database=salesforce`` can create, update, rename or delete
custom models and custom fields. It works with all Python and Django versions supported by django-salesforce.
It is however recommended to use versions supported by mainstream: Python >= 3.6 and Django >= 2.2.


Quick start
...........

.. code:: shell

    # before running an initial migration in a new Salesforce database
    python manage.py migrate --database=salesforce --sf-create-permission-set

Then add some custom objects (models) to Salesforce and some custom fields e.g. also to a standard object
"Contact".

``models.py``:

.. code:: python

    class Contact(SalesforceModel):
        # we add a custom field "my_field" to a standard object "Contact"
        last_name = models.CharField(max_length=50)
        my_field = models.CharField(max_length=50, null=True, sf_managed=True)

    class MyObject(SalesforceModel):
        # a field with API name "Name" is created automatically by SFDC and its "max_length" is ignored.
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

Add them to Salesforce

.. code:: shell

    # for every migration
    python manage.py makemigrations
    python manage.py migrate --database=salesforce


More advanced
.............

This simple method of operation works well on a new empty development Salesforce instance,
but even with a sandbox created from an existing production database it should be more complicated.
A general practice with Saleforce is that more packages made by different vendors are installed
by the organization. Not all custom objects and fields should be therefore managed by Django.

An extended version of ``migrate`` command is installed by django-salesforce. Four new options are added by it.
``--sf-create-permission-set``, ``--sf-debug-info``, ``--sf-interactive``, ``--sf-no-check-permissions``.
These options are checked only for databases on salesforce.com (SFDC) and are ignored for other databases.

| The management by Django modifies SFDC only if it is  
| A) explicitly enabled by the Django model and also  
| B) it must be enabled in Salesforce administration  
| C) more conditions must be met on production databases.
|

**A\)** How to enable migrations in Django

Custom object in Salesforce that should be created and managed by Django must use the Meta option: ``sf_managed = True``.

Custom fields can be created and managed also in objects not managed by Django if a field is marked
by a parameter ``sf_managed=True`` in a field definition.

**B\)** How must be migrations enabled also in Salesforce administration.

A basic security feature is that a permission set "Django_Salesforce" must be created by the command
``python manage.py migrate --database=salesforce --sf-create-permission-set``
before any migration can run on SFDC.

A custom table can be deleted or renamed by Django only if it has been created by Django originally.
(More precisely: All object permissions are automatically assigned to a Salesforce object (table)
in "Django_Salesforce" Permission Set when it is created by Django,
including "PermissionsModifyAllRecords". It is later verified before an object is deleted or renamed.)

A custom field can be modified or deleted by Django if at least one field has been created by Django
in that table. (More precisely: The object permission "PermissionsEdit" is assigned to a Salesforce
in "Django_Salesforce" Permission Set when a custom field is created by Django.
No field can be modified or deleted by Django in a table without this ObjectPermission.)

**C\)** Security on production databases

Another security feature is that all destructive operations (``delete_model`` and ``remove_field``)
are interactive on production databases. Every delete must be confirmed like
if an option ``--sf-interactive`` was used, but no dialog is after any error and the migration is always
terminated (unlike '--sf-interactive').

Troubleshooting
...............

Migrations are excellent in develomment especially if they are used since the beginning.
They can be problematic if management by Django has been combined with some manual
administration of the same objects or if an application should work on an existing instance
and on a new empty instance.

An ``--sf-interactive`` allows to interactively skip
any individual part of migration and eventually to continue if you are sure that ane error can be ignored,
e.g. if it failed because a duplicit object has beens created or an object should be deleted,
but it has been deleted previously.
It allows to normally terminate or to ignore an error or to start debugging.

.. code::

    $ python manage.py migrate --sf-interactive --database=salesforce ...

    Running migrations:
        Applying example.0001_initial...
    create_model(<model Test>)
    Run this command [Y/n]: n

My answer ``**migrate --fake** at Stackoverflow <https://stackoverflow.com/a/46774336/448474>``
can be useful how the migration state can be set if you know how many initial migrations were applied
manually on an instance before the migration system is enabled on it.

The option ``--sf-debug-info`` will print a short useful context about an error before raising an exception
or before an error message if the was not raised in interactive mode .

The option ``--sf-no-check-permissions`` is useful if the database contains no important data,
but the migration state is lost out of sync and you want to go to the initial state and migrate again.
Then this combination of parameters could be useful:

.. code:: shell

   python manage.py migrate --database=salesforce my_application --sf-interactive --noinput --sf-no-check-permissions --sf-debug-info
   python manage.py migrate --database=salesforce my_application zero --sf-interactive --noinput --sf-no-check-permissions --sf-debug-info
   python manage.py migrate --database=salesforce my_application

The combination of ``--sf-interactive --noinput`` means that all question "Run this command?"
are answered "Y(es)" and all questions "Stop after this error?" are answered "c(ontinue)".


Reference
.........

| **Terminology**:  
| **Model** in Django terminology is an equivalent of **Table** in database terminology and an equivalent of **Object** in Salesforce terminology. These three points of view are used in this text.  
|  
| **Builtin** object and builtin field  have a name without any double underscore ``'__'``.  
| **Custom** object and custom field ore in the form ``ApiName__c`` with only a suffix ``__c`` and without any other double underscore.  
| **Namespace** object and namespace field are in the form ``NameSpace__ApiName__c``.  
|  |  
| Because custom fields can be managed by Django automatically in SFDC the algorithm of conversion a name to db_column is guaranteed stable then the db_column is not so important as before.  

| If no **db_column** is specified then it can be derived from "django field name" this way:  
| If the django field name is not lower case then the default api name is the same.  
| Default API name from a lower case name is created by capitalizing and removing spaces:  
| e.g. default api name "LastModifiedDate" can be created from "last_modified_date" or from "LastModifiedDate".  
| Custom field can be rocognized by "custom=True".  
| Namespace field can be recognized by "sf_prefix='NameSpacePrefix'".  
| All unspecified fields without "db_column" in custom objects are expected custom field, except a few standard well known system names like "LastModifiedDate".  
|  
| If you find a new not recognized system name then report it as a bug and specify an explicit "custom=False" or an explicit "db_column=...", but it is extremely unprobable because I verify all system names in a new API before I enable that API version in a new version of django-salesforce.  


All fields that can be managed by Django in SFDC are entirely explicitly identified in ``migrations/*.py``
by a parameter ``sf_managed=True``. The right value ``field.sf_managed`` can be usually derived correctly from a simple
model ``models.py`` with minimum of `sf_managed`` options:

- Custom fields in sf_managed custom object are sf_managed by default.
- Custom fields in non sf_managed objects are not sf_managed by default.
- Builtin fields and namespace fields and builtin objects and namespace objects should be never sf_managed.
- The "Name" field (a field with db_column='Name') is a special part of a database Object and
  its sf_managed values is not important. Its ``sf_managed=`` should be omitted or it should be the same
  as the value of the object.

The table with a label "migrations" has a name "django_migrations__c" on SFDC. It is created by the first "migrate" command.

| 2) Custom object in Salesforce that should be created and managed by Django must use the Meta option: ``sf_managed = True``.
Custom fields can be created also in objects not managed by Django if a field is marked by a parameter ``sf_managed=True``.

Custom fields in objects managed by Django are also managed by Django by default,
but it is possible to set a parameter ``sf_managed=False`` to disable it.

Objects and fields created by Django are enabled in Django_Salesforce permission set and can be
also modified and deleted by Django. If an existing sf_managed object is not enabled
in the pemission set then it is skipped with a warning and its settings can not be modified.

If you want to start to manage an object that has been created manually then enable all
Object Permissions for that object in "Django_Salesforce" permission set even if the field
is accessible still by user profiles.


Unimplemented features - caveats
................................

The implementation is kept simple until usefulness of migrations will be appreciated enough.

All migration operations are currently implemented without transactions and without
any optimization. Every field is processed by an individual command.

It is not possible to detect only a change of model Meta options ``verbose_name`` or ``verbose_name_plural``.
You should change change also something unimportant in the ``Name`` field of that model
in the same transaction e.g. change the unused ``max_length`` parameter or add a space
at the end of ``verbose_name`` of Name field. That will trigger update of metadata of
the CustomObject in Salesforce.

Maybe a special NameField will be implemented, because it has a fixed option "null=False" ("required=True")
and special options "dataType", "displayFormat" and "startingNumber" not yet implemented. CharField
is good enough without them. Data type "Automatic Number" is derived from "sf_read_only=models.READ_ONLY",
otherwise the data type is "Text"

There is a risk that a field can not be created because e.g. a duplicit related name exist in trash bin
and also that a field can not be deleted because it is used by something important in Salesforce.
That are usual problems also with manual administrations, but that could cause an inconsistent migration,
because a transaction is not currently used. Therefore if you want to use migrations in production,
verify it, debug it on a sandbox, then create a fresh sandbox from production and verify the migration again.

Master-Detail Relationship is not currently implemented even that it is an important type.

All deleted objects and fields remain in a trash bin and they are not purged on delete.

It works currently in slow mode that modifies every field and every table individually.
That mode is useful for troubleshooting if some object is locked by something in some 
Salesforce instance and that mode can be easily switched to an interactive mode.

A transactional mode should be however written where every migration will change correctly
all or nothing. That will be mostly necessary for use in production.

It is tested manually and mo automatic test exist for migrations on SFDC.
