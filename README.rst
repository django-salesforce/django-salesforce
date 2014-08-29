django-salesforce
=================

.. image:: https://travis-ci.org/freelancersunion/django-salesforce.svg?branch=master
   :target: https://travis-ci.org/freelancersunion/django-salesforce

This library allows you to load and edit the objects in any Salesforce instance
using Django models. The integration is fairly complete, and generally seamless
for most uses. It works by integrating with the Django ORM, allowing access to
the objects in your SFDC instance as if they were in a traditional database.

Python 2.6, 2.7, 3.3, 3.4 or pypy; Django 1.4.2 - 1.7. Note that Django 1.4.x
is not compatible with Python 3.

Quick Start
-----------

1. Install django-salesforce: ``pip install django-salesforce``

2. Add the ``salesforce`` app to your ``INSTALLED_APPS`` setting::

    INSTALLED_APPS = {
        "django.contrib.auth",
        "django.contrib.contenttypes",
        ...
        ...
        "salesforce"
    }


3. Add a salesforce connection to your ``DATABASES`` setting::

    'salesforce': {
        'ENGINE': 'salesforce.backend',
        "CONSUMER_KEY" : '',
        "CONSUMER_SECRET" : '',
        'USER': '',
        'PASSWORD': '',
        'HOST': 'https://test.salesforce.com',
    }


4. **(optional)** To override the default timeout of 15 seconds,
   define ``SALESFORCE_QUERY_TIMEOUT`` in your settings file::

    SALESFORCE_QUERY_TIMEOUT = 15

5. **(optional)** If you want to use another name for your Salesforce DB
   connection, define ``SALESFORCE_DB_ALIAS`` in your settings file::

    SALESFORCE_DB_ALIAS = 'salesforce'

6. Add ``salesforce.router.ModelRouter`` to your ``DATABASE_ROUTERS``
   setting::

    DATABASE_ROUTERS = [
        "salesforce.router.ModelRouter"
    ]

7. Define a model that extends ``salesforce.models.SalesforceModel``
   or export the complete SF schema by
   ``python manage.py inspectdb --database=salesforce`` and simplify it
   to what you need.

8. You're all done! Just use your model like a normal Django model.

Primary Key
-----------
Primary keys are added to models only automatically,
because SFDC doesn't allow to define custom primary key. The lowercase name of
primary key `id` can be configured globally for the project in its settings by
`SF_PK='id'`. The backward compatible name `Id` is useful only for old projects,
though it will stay as the default variant until `django-salesforce>=0.5`.

Foreign Key Support
-------------------

**Foreign key** filters are currently possible only for the first level of
relationship and only for fields whose name equals the name of object.
Foreign keys of an object can be normally accessed by dot notation without any
restriction
Example::

    contacts = Contact.objects.filter(Account__Name='FOO Company')
    print(contacts[0].Account.Owner.LastName)

But the relationship ``Owner__Name`` is not currently possible because the
type of ``Owner`` is a different name (``User``).

Along similar lines, it's not currently possible to filter by `ForeignKey`
relationships based on a custom field. This is because related objects
(Lookup field or Master-Detail Relationship) use two different names in
`SOQL <http://www.salesforce.com/us/developer/docs/soql_sosl/>`__. If the
relation is by ID the columns are named `FieldName__c`, whereas if the relation
is stored by object the column is named `FieldName__r`. More details about
this can be found in the discussion about `#43 <https://github.com/freelancersunion/django-salesforce/issues/43>`__.

In case of a ForeignKey you can specify the field name suffixed with ``_id``,
as it is automatically allowed by Django. For example: ``account_id`` instead
of ``account.id``, or ``AccountId`` instead of ``Account.Id``. It is faster,
if you need not to access to the related ``Account`` object.

Querysets can be easily inspected whether they are correctly compiled to SOQL.
You can compare the meaning with the same compiled to SQL::

    my_qs = Contact.objects.filter(my__little_more__complicated='queryset')
    print my_qs.query.get_compiler('salesforce').as_sql()    # SOQL
    print my_qs.query.get_compiler('default').as_sql()       # SQL

**Generic foreign keys** are frequently used in SF for fields that relate to
objects of different types, e.g. the Parent of Note or Attachment can be almost
any type of ususal SF objects. Filters by `Parent.Type` and retrieving this
type is now supported::

    note = Note.objects.filter(parent_type='Contact')[0]
    parent_model = getattr(example.models, note.parent_type)
    parent_object = parent_model.objects.get(pk=note.parent_id)
    assert note.parent_type == 'Contact'

Example of `Note` model is in `salesforce.testrunner.example.models.Note`.

Advanced usage
--------------

-  **Testing** - By default, tests will be run against the SFDC connection
   specified in settings.py, which will substantially increase testing time.
   
   One way to speed this up is to change the SALESFORCE_DB_ALIAS to point to
   another DB connection (preferably SQLite) during testing using the
   ``TEST_*`` settings variables. The only outbound connections will then be to
   the authentication servers.
   
-  **Multiple SFDC connections** - In most cases, a single connection is all
   that most apps require, so the default DB connection to use for Salesforce
   is defined by the ``SALESFORCE_DB_ALIAS`` settings variable. This behavior
   can be also configured by ``DATABASE_ROUTERS``, replacing the use of
   salesforce.backend.router.ModelRouter.

-  **Non SF databases** - If ``SALESFORCE_DB_ALIAS`` is set to a conventional
   database, the tables defined by the SF models will be created by syncdb. This
   behavior can be disabled by adding a Meta class with ``managed=False``.

-  **Custom Managers** - When creating a custom manager for a model, the manager
   must be a descendant of ``salesforce.manager.SalesforceManager``.
   
   In most cases, switching DB connections with ``.using(alias).`` will be
   sufficient, but if you need to call a method on your custom manager, you should
   instead use ``.db_manager(alias)`` to select a DB while returning the correct
   manager, e.g. ``Contact.objects.db_manager(alias).my_manager(params...)``

-  **Automatic Field Naming** - Most of database columns names can be automatically
   deduced from Django field name, if no ``db_column`` is specified::

     last_name = models.CharField(max_length=80)     # db_column='LastName'
     FirstName = models.CharField(max_length=80)    # db_column='FirstName'
     custom_bool = models.BooleanField(custom=True)  # db_column='CustomBool__c'
   
   Fields named with an upper case character are never modified, except for the
   addition of the namespace prefix or the '__c' suffix for custom fields.

-  **Custom SF Objects and Fields** - Custom SF class objects are indicated by
   adding a Meta class with parameter 'custom=True'. All child fields are
   assumed to be custom as well, unless marked otherwise with a field parameter
   marked "custom=False".

   Similarly, custom fields on standard objects can be indicated by "custom=True",
   or they can be defined in an standard parent model (the ``custom`` Meta
   parameter is not inherited). 

   Also namespace prefixes of managed packages (prefixed with "PackageName\__"
   can be automatically applied to custom fields without db_column.

-  **Meta class options** - If an inner ``Meta`` class is used, it must be a
   descendant of ``SalesforceModel.Meta`` or must have ``managed=False``.

-  **Database Introspection with inspectdb** Tables that are exported into a
   Python model can be restricted by regular expression::

     python manage.py inspectdb --table-filter="Contact$|Account" --database=salesforce

   In this example, inspectdb will only export models for tables with exact
   name ``Contact`` and all tables that are prefixed with ``Account``. This
   filter works with all supported database types.

-  **Inheritance from multiple abstract models** is very useful for Salesforce,
   because the same sets of fields are frequently used in many models, but with
   a hierarchy with one ancestor would be too deep, rigid and complicated.
   Also proxy models and mixins are supported.


Caveats
-------

This package is in continuous development, and the ultimate goal is to
support all reasonable features of the Salesforce platform, but for now
here are the potential pitfalls and unimplemented operations:

-  **Large Objects** — Since the entire result set needs to be transferred
   over HTTP, and since it's common to have extremely high column counts
   on full object queries, it's assumed that users will create models that
   are specific to their individual applications' needs. Models that have
   been included with this library are for example and documentation
   purposes.
-  **Inheritence** — When using the default router, all models for object
   types on Salesforce must extend salesforce.models.SalesforceModel. The
   model router checks for this to determine which models to handle through
   the Salesforce connection.
-  **Multiple Updates** — Multiple update support is not yet
   implemented.
-  **Multiple Deletes** — Multiple delete support is not yet
   implemented.
-  **Database Sync** — ``syncdb`` will only create new databases in non-SF
   databases (useful for unit tests); SFDC classes are assumed to already
   exist with the appropriate permissions.

Experimental Features
---------------------

-  The requirement that "ModelAdmin should extend
   ``salesforce.admin.RoutedModelAdmin``" is probably not important any more
   in your custom admin.py. It is still required if you use multiple Salesforce
   databases and multiple instances of AdminSite etc.

-  **Dynamic authorization** - Expect that you have another application for
   Salesforce e.g. a mobile application, where is still know the
   `Access Token <https://www.salesforce.com/us/developer/docs/api_rest/Content/quickstart_oauth.htm>`
   for a current user. You want to send a request 
   to your django-salesforce application to do anything under credentials of that current user.
   Then is not necessary to save any credentials for SFDC into Django settings.
   It is not solved, how you get the token or how you send it to Django
   (usually in the `Authorization:` header).

   Set this to your ``DATABASES`` setting::

    'salesforce': {
        'ENGINE': 'salesforce.backend',
        'HOST': 'https://your-site.salesforce.com',
        'CONSUMER_KEY': '.',
        'CONSUMER_SECRET': '.',
        'USER': 'dynamic auth',
        'PASSWORD': '.',
    }


   Items with `'.'` value are not important for `dynamic auth`, but can not be
   empty due to some validity checks.

   Create some middleware that is called at the beginning of request::

    from django.db import connections

        # get 'access_token' by yourself... and
        # put it into salesforce connection
        connections['salesforce'].sf_session.auth.dynamic_start(access_token)

   Forget the access token at the end of request::

        connections['salesforce'].sf_session.auth.dynamic_end()

   SFDC can be used with a normal static auth before dynamic_start and after
   dynamic_end.
