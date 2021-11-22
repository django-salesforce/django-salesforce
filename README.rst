django-salesforce
=================

.. image:: https://travis-ci.org/django-salesforce/django-salesforce.svg?branch=master
   :target: https://travis-ci.org/django-salesforce/django-salesforce

.. image:: https://badge.fury.io/py/django-salesforce.svg
   :target: https://pypi.python.org/pypi/django-salesforce

.. image:: https://img.shields.io/badge/python-3.6%20%7C%203.7%20%7C%203.8%20%7C%203.9%20%7C%203.10-blue
   :target: https://www.python.org/

.. image:: https://img.shields.io/badge/Django-2.0%2C%202.1%2C%202.2%20%7C%203.0%2C%203.1%20%2C%203.2%20%7C%204.0-blue.svg
   :target: https://www.djangoproject.com/

This library allows you to load, edit and query the objects in any Salesforce instance
using Django models. The integration is fairly complete, and generally seamless
for most uses. It works by integrating with the Django ORM, allowing access to
the objects in your SFDC instance (Salesforce .com) as if they were in a
traditional database.

Python 3.5.3 to 3.10, Django 2.0 to 4.0.


Quick Start
-----------

Install, configure a Salesforce connection, create a Salesforce model and run.

1. Install django-salesforce: ``pip install django-salesforce``

2. Add a salesforce connection to your ``DATABASES`` setting::

    'salesforce': {
        'ENGINE': 'salesforce.backend',
        'CONSUMER_KEY': '',                # 'client_id'   in OAuth2 terminology
        'CONSUMER_SECRET': '',             # 'client_secret'
        'USER': '',
        'PASSWORD': '',
        'HOST': 'https://test.salesforce.com',
    }

   In the example above, all fields should be populated as follows:

   * ``CONSUMER_KEY`` and ``CONSUMER_SECRET`` values are for the app used to
     connect to your Salesforce account. Instructions for how get these are in
     the Salesforce REST API Documentation. Key and secret can be created on
     web by:

     - Salesforce Classic > Setup > App Setup > Create > Apps > Connected apps >
       New.  
       or SalesForce Lightning > Setup > Apps > App Manager > New Connected App.
     - Click "Enable OAuth Settings" in API, then select "Access and manage
       your data (api)" from available OAuth Scopes.
     - Other red marked fields must be filled, but are not relevant for Django
       with password authentication. ("Callback URL" should be a safe URL
       that maybe doesn't exist, but is under your control and doesn't redirect,
       for the case that you accidentally activate other OAuth mode later.)
   * ``USER`` is the username used to connect.
   * ``PASSWORD`` is a concatenation of the user's password and security token.
     Security token can be set by My Settings / Personal / Reset My Security Token
     or an new token is received by email after every password change.
     Security token can be omitted if the local IP address has been
     whitelisted in Security Controls / Network Access.
   * ``HOST`` is ``https://test.salesforce.com`` to access a sandbox, or
     ``https://login.salesforce.com`` to access production.

   If an error occurs in a request to Salesforce, review the received error message
   that is exactly copied between braces ``{...}`` from the
   Salesforce response to a Python exception to assist debugging.

   See also: `Information on settings up Salesforce connected apps
   <https://help.salesforce.com/apex/HTViewHelpDoc?id=connected_app_create.htm>`_
   if necessary.

   **Note about permissions**: Administrator rights are only required to run
   the full suite of unit tests; otherwise, as long as the account has rights to
   read or modify the chosen object, everything should work properly.
   Introspection by ``inspectdb`` doesn't require any object permissions.

3. Add ``salesforce.router.ModelRouter`` to your ``DATABASE_ROUTERS``
   setting::

    DATABASE_ROUTERS = [
        "salesforce.router.ModelRouter"
    ]

   (This is important for switching between 'salesforce' database for
   models derived from SalesforceModel and 'default' database for normal models
   with tables created by migrations, especially for 'django.contrib'.)

4. Add the ``salesforce`` app to your ``INSTALLED_APPS`` setting::

    INSTALLED_APPS = {
        "django.contrib.auth",
        "django.contrib.contenttypes",
        ...
        ...
        "salesforce"
    }

   (This is necessary for running Salesforce extensions in the command
   ``inspectdb --database=salesforce`` in development, otherwise it is
   not important.)


5. Define a model that extends ``salesforce.models.Model`` (alias ``SalesforceModel``)
   or export the complete SF schema by ``python manage.py inspectdb --database=salesforce``
   and simplify it to what you need. The full models file is about 2 MB with 500 models
   and the export takes 2 minutes, but it is a valid models module that works without
   modification. The output of command ``inspectdb`` can be restricted by a list
   of table_names on the command line, but also ForeignKey fields to omitted models
   must be pruned to get a valid complete small model.

6. **(optional)** To override the default timeout of 15 seconds,
   define ``SALESFORCE_QUERY_TIMEOUT`` in your settings file.
   It can be one number or better a tuple with a short value for connection
   timeout and a longer value that includes time for running a query.
   It never need be longer than 30 seconds::

    SALESFORCE_QUERY_TIMEOUT = (4, 15)  # default (connect timeout, data timeout)

7. **(optional)** If you want to use another name for your Salesforce DB
   connection, define ``SALESFORCE_DB_ALIAS`` in your settings file::

    SALESFORCE_DB_ALIAS = 'salesforce'  # default

8. You're all done! Just use your model like a normal Django model.

9. **(optional)** Create a normal Django ``admin.py`` module for your Salesforce models
   and you can register a minimalistic admin for all omitted Admin classes::

    from salesforce.testrunner.example.universal_admin import register_omitted_classes
    # some admin classes that you wrote manually yet
    # ...
    # end of file
    register_omitted_classes(your_application.models)

   This is a rudimentary way to verify that every model works in a sandbox, before
   hand-writing all admin classes. (Foreign keys to huge tables in the production
   require a customized admin e.g. with search widgets.)
    
10. **(optional)** By default, the Django ORM connects to all DBs at startup. To delay
    SFDC connections until they are actually required, define ``SF_LAZY_CONNECT=True``
    in your settings file. Be careful when using this setting; since it won't fail during
    the application boot, it's possible for a bad password to be sent repeatedly,
    requiring an account reset to fix.

Primary Key
-----------
Salesforce doesn't allow you to define custom primary keys, so django-salesforce
will add them automatically in all cases. You can override only capitalization and use
a primary key ``Id`` by configuring ``SF_PK='Id'`` in your project settings
if you prefer Salesforce capitalized field name conventions instead of Django
default ``id``.

Advanced usage
--------------
-  **Multiple Inheritance from Abstract Models** - Many Salesforce models use
   the same sets of fields, but using a single inheritance tree would be too
   complicated and fragile. Proxy models and mixins are also supported.

-  **Testing** - By default, tests will be run against the SFDC connection
   specified in settings.py, which will substantially increase testing time.

   One way to speed this up is to change the SALESFORCE_DB_ALIAS to point to
   another DB connection (preferably SQLite) during testing using the
   ``TEST`` settings variable. Such simple tests can run without any network
   access. Django unit tests without SalesforceModel
   are fast everytimes. Special read only fields that are updated only by SFDC
   e.g. ``last_modified_date`` need more parameters to be possible to save them
   into an alternate database, e.g. by ``auto_now=True`` or to play with
   ``null=True`` or ``default=...``.
   
-  **Multiple SFDC connections** - In most cases, a single connection is all
   that most apps require, so the default DB connection to use for Salesforce
   is defined by the ``SALESFORCE_DB_ALIAS`` settings variable. This behavior
   can be also configured by ``DATABASE_ROUTERS``, replacing the use of
   salesforce.router.ModelRouter.

-  **Non SF databases** - If ``SALESFORCE_DB_ALIAS`` is set to a conventional
   database, the tables defined by the SF models will be created by ``migrate``. This
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
     FirstName = models.CharField(max_length=80)     # db_column='FirstName'
     my_bool = models.BooleanField(custom=True)      # db_column='MyBool__c'
   
   Fields named with an upper case character are never modified, except for the
   addition of the namespace prefix or the '__c' suffix for custom fields.
   If you want models with minimal db_column then read
   `Running inspectdb <https://github.com/django-salesforce/django-salesforce/wiki/Introspection-and-Special-Attributes-of-Fields#running-inspectdb>`__.

-  **Query deleted objects** - Deleted objects that are in trash bin are
   not selected by a normal queryset, but if a special method ``query_all``
   is used then also deleted objects are searched.
   If a trash bin is supported by the model then a boolean field ``IsDeleted``
   can be in the model and it is possible to select only deleted objects ::

     deleted_list = list(Lead.objects.filter(IsDeleted=True).query_all())

-  **Migrations** - Migrations can be used for an alternate test database
   with SalesforceModel. Then all tables must have Meta options ``db_table``
   and fields must have option ``db_column``, which is done by ``inspectdb``
   with default settings. Models exported by introspection ``inspectdb``
   do not specify the option ``managed`` because the default value is True.

   Models managed by migrations on SFDC require the option ``sf_managed=True``.
   Detaild are described in `docs Migrations <docs/migrations.rst>`__.

   (It is safe. When migrations in SFDC will be supported by the next version
   4.0.1 then only for explicitly selected fields and models and on
   explicitly labeled SFDC databases.
   Consequently, the setting ``managed = True`` alone is related only to
   an alternate non SFDC database configured by ``SALESFORCE_DB_ALIAS``.)

   There is probably no reason now to collect old migrations of an application
   that uses only SalesforceModel if they are related to data stored only in Salesforce.
   Such old migrations can be easily deleted and a new initial migration can be
   created again if it would be necessary for offline tests if that migrations
   directory seems big and obsoleted.

-  **Exceptions** - Custom exceptions instead of standard Django database
   exceptions are raised by Django-Salesforce to get more useful information.
   General exceptions are ``SalesforceError`` or a more general custom
   ``DatabaseError``. They can be imported from ``salesforce.dbapi.exceptions``
   if database errors should be handled specifically in your app.

Foreign Key Support
-------------------
Foreign key relationships should work as expected, but mapping
Salesforce SOQL to a purely-relational mapper is a leaky abstraction. For the
gory details, see `Foreign Key Support <https://github.com/django-salesforce/django-salesforce/wiki/Foreign-Key-Support>`__
on the Django-Salesforce wiki.

Introspection and special attributes of fields
----------------------------------------------
Some Salesforce fields can not be fully used without special attributes, namely
read-only and default value fields. Further details can be found in
`Introspection and Special Attributes of Fields <https://github.com/django-salesforce/django-salesforce/wiki/Introspection-and-Special-Attributes-of-Fields>`__

Caveats
-------

The ultimate goal of development of this package is to support reasonable
new features of the Salesforce platform and of new Django versions,
but for now here are the potential pitfalls and unimplemented operations:

-  **Large Objects** — Since the entire result set needs to be transferred
   over HTTP, and since it's common to have extremely high column counts
   on full object queries, it's assumed that users will create models that
   are specific to their individual applications' needs. It is especially
   important if migrations should be created. Migrations on the full models
   module are really slow. (Models that have been included with this library are
   very simplified only for example and documentation purposes and for tests.)
-  **Inheritance** — When using the default router, all models Salesforce
   must extend salesforce.models.SalesforceModel. The model router checks
   for this to determine which models to handle through the Salesforce
   connection.
-  **Database Migrations** — ``migrate`` will create new tables only in non-SF
   databases (useful for unit tests); SFDC tables are assumed to already
   exist with the appropriate permissions.

-  **Unsupported methods**: Queryset methods ``union()``, ``difference()``,
    ``intersection()`` and ``distinct()``
    are e.g. not supported because SOQL doesn't support corresponding operators:
    UNION, EXCEPT, INTERSECT and DISTINCT.

Backwards-incompatible changes
------------------------------

The most important:

-  v4.0: Removed support for Python 3.5

-  v3.2: Removed support for Django 1.11

-  v1.0: The object ``salesforce.backend.operations.DefaultedOnCreate`` in an incidental
   old migration should be rewritten to new ``salesforce.fields.DefaultedOnCreate``, but
   old migrations are unnecessary usually.

-  v0.9: This is the last version that suports Django 1.10 and Python 2.7 and 3.4

-  v0.8: The default Meta option if now ``managed = True``, which is an important
   change for non-Salesforce databases (see about Migrations above).

   Completely different implementation of raw queries and cursor that is compatible
   with normal databases. (a more backward compatible option can be added if
   it will be required)

   Custom exception classes has been moved to ``salesforce.dbapi.exceptions``.

-  v0.7.2: This is the last code that supports old Django 1.8.4+ and 1.9

-  v0.6.9: This is the last code that supports old Django 1.7 and 1.8.0 - 1.8.3

-  v0.6.1: This is the last code that supports old Django 1.4, 1.5, 1.6.

-  v0.5: The name of primary key is currently ``'id'``. The backward compatible
   behavior for code created before v0.5 can be reached by settings ``SF_PK='Id'``.
