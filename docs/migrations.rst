Migrations
==========

new in v3.2.1.

Migrations are supported in Salesforce databases on SFDC site.
The command ``python manage.py migrate --database=salesforce`` can create, update, rename or delete
custom models and custom fields. It works with all Python and Django versions supported by django-salesforce.
It is however recommended to use version supported by mainstream: Python >= 3.6 and Django >= 2.2.

Quick start:

.. code:: python

    # for the first time
    python manage.py migrate --database=salesforce --sf-create-permission-set

    # every migration
    python manage.py makemigrations
    python manage.py migrate --database=salesforce

The extended version of ``migrate`` command is installed in django-salesforce. Four new options are added in it.
``--sf-create-permission-set --sf-debug-info --sf-interactive --sf-no-check-permissions``
That modifies running on SFDC. It has no impact on other databases.

A general practice with Saleforce is that more packages made by more vendors are installed
by the organization. Not all custom objects and fields should be therefore managed by Django.
The management by Django modifies Salesforce only if it is explicitly enabled
by the Django model and also enabled in Salesforce administration.
A custom table can be deleted  by Django only if it was created by Django.
No field can be deleted by Django in a table if at least one field has been not created in that table.
This prevents some mistakes that some part of the database are managed unitentionally.

Another security feature is that all destructive operations ``delete_model`` and ``remove_field``
are interactive on production databases and every delete must be confirmed like
if option ``--sf-interactive`` was used.

If and only if you want to run migrations on a Salesforce database then:

| 1) Create a permission set with the API name ``Django_Salesforce`` and assign it to the current user
by the command:  
|    ``python manage.py migrate --database=salesforce --sf-create-permission-set``  


The table "django_migrations__c" has a label "migrations" and it is created by the first "migrate" command.
| 2) Custom object in Salesforce that should be created and managed by Django must use the Meta option: ``sf_managed = True``.
Custom fields can be created also in objects not managed by Django if a field is marked by a parameter ``sf_managed=True``.

Example:

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


.. code:: shell

    $ python manage.py makemigrations
    $ python manage.py migrate --database=salesforce

Custom fields in objects managed by Django are by default managed by Django,
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

Maybe a special NameField will be implemented, because it has a fixed option "null=False" ("required=True")
and special options "dataType", "displayFormat" and "startingNumber" not yet implemented. CharField
is good enough without them. Data type "Automatic Number" is derived from "sf_read_only=models.READ_ONLY",
otherwise the data type is "Text"

There is a risk that a field can not be created becase e.g. a duplicit related name exist in trash bin
and also that a field can not be deleted because it is used by something important in Salesforce.
That are usual problems also with manual administrations, but that could cause an uncosistent migration,
because a transaction is not currently used. There if you want to use migrations in production,
verify debug it on a sandbox, then create a fresh sandbox from production and verify the migration again.

Master-Detail Relationship is not currently implemented even that it is an important type.

All deleted objects and fields remain in a trash bin and they are not purged on delete.
