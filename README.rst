django-salesforce
=================

.. image:: https://travis-ci.org/django-salesforce/django-salesforce.svg?branch=master
   :target: https://travis-ci.org/django-salesforce/django-salesforce

.. image:: https://badge.fury.io/py/django-salesforce.svg
   :target: https://pypi.python.org/pypi/django-salesforce

.. image:: https://img.shields.io/badge/Python-2.7.9%2B%2C%203.4%2C%203.5-brightgreen.svg
   :target: https://www.python.org/

.. image:: https://img.shields.io/badge/Django-1.8.4%2B%2C%201.9%2C%201.10%2C%201.11-blue.svg
   :target: https://www.djangoproject.com/

This library allows you to load and edit the objects in any Salesforce instance
using Django models. The integration is fairly complete, and generally seamless
for most uses. It works by integrating with the Django ORM, allowing access to
the objects in your SFDC instance (Salesforce .com) as if they were in a
traditional database.

Python 2.7.9+, 3.4 to 3.6, Django 1.8.4+, 1.9, 1.10, 1.11 are supported with
some limitations on raw queries, values_list() and values() methods.

Django 1.10 and 1.11 is currently supported without values(), values_list(), defer(),
some raw() methods. (All fixed in a development repository, waiting for review,
consensus etc.)

Pre-2.7.9 Python versions don't have the required TLS 1.1 support to use
both production and sandbox Salesforce instances. PyPy may still work,
but currently it's a challenge to get a PyPy build linked to a recent
version of libssl.

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
        'CONSUMER_KEY': '',
        'CONSUMER_SECRET': '',
        'USER': '',
        'PASSWORD': '',
        'HOST': 'https://test.salesforce.com',
    }

   In the example above, all fields should be populated as follows:

   * ``CONSUMER_KEY`` and ``CONSUMER_SECRET`` values are for the app used to
     connect to your Salesforce account. Instructions for how get these are in
     the Salesforce REST API Documentation. Key and secret can be created on
     web by:

     - Salesforce web > Setup > App Setup > Create > Apps > Connected apps >
       New.
     - Click "Enable OAuth Settings" in API, then select "Access and manage
       your data (api)" from available OAuth Scopes.
     - Other red marked fields must be filled, but are not relevant for Django.
   * ``USER`` is the username used to connect.
   * ``PASSWORD`` is a concatenation of the user's password and security token.
     Security token can be omitted if the local IP address has been
     whitelisted in Security Controls / Network Access.
   * ``HOST`` is ``https://test.salesforce.com`` to access a sandbox, or
     ``https://login.salesforce.com`` to access production.

   If an error message is received while connecting, review the error received.
   Everything in the error message between ``{...}`` is exactly copied from the
   Salesforce error message to assist debugging.

   See also: `Information on settings up Salesforce connected apps
   <https://help.salesforce.com/apex/HTViewHelpDoc?id=connected_app_create.htm>`_.

   **Note about permissions**: Everything for a project can work under
   restricted Salesforce user account if it has access to objects in your
   models. Introspection (inspectdb) doesn't require any permissions. Running
   tests for django_salesforce requires many permissions or Administrator
   account for sandbox.
   
   **Note about permissions**: Administrator rights are only required to run
   the full suite of unit tests; otherwise, as long as the account has rights to
   read or modify the chosen object, everything should work properly.

4. Add ``salesforce.router.ModelRouter`` to your ``DATABASE_ROUTERS``
   setting::

    DATABASE_ROUTERS = [
        "salesforce.router.ModelRouter"
    ]

5. Define a model that extends ``salesforce.models.Model`` or export the
   complete SF schema by ``python manage.py inspectdb --database=salesforce``
   and simplify it to what you need.

6. **(optional)** To override the default timeout of 15 seconds,
   define ``SALESFORCE_QUERY_TIMEOUT`` in your settings file::

    SALESFORCE_QUERY_TIMEOUT = 15  # default

7. **(optional)** If you want to use another name for your Salesforce DB
   connection, define ``SALESFORCE_DB_ALIAS`` in your settings file::

    SALESFORCE_DB_ALIAS = 'salesforce'  # default

8. You're all done! Just use your model like a normal Django model.

9. **(optional)** Create a normal Django ``admin.py`` module for your Salesforce model::

    from salesforce.testrunner.example.universal_admin import register_omitted_classes
    # some admin classes that you wrote manually yet
    # ...
    # end of file
    register_omitted_classes(your_application.models)

   This is a rudimentary way to verify that every model works in sandbox, before
   hand-writing all admin classes. (Foreign keys to huge tables in the production
   require customized admins e.g. with search widgets.)
    
10. **(optional)** By default, the Django ORM connects to all DBs at startup. To delay
    SFDC connections until they are actually required, define ``SF_LAZY_CONNECT=True``
    in your settings file. Be careful when using this setting; since it won't fail during
    the application boot, it's possible for a bad password to be sent repeatedly,
    requiring an account reset to fix.

Primary Key
-----------
Salesforce doesn't allow you to define custom primary keys, so django-salesforce
will add them automatically in all cases. You can override capitalization and use
primary key ``id`` by configuring ``SF_PK='id'`` in your project settings. The previous
capitalization of ``Id`` is only for old projects, but it will stay as the default
variant until ``django-salesforce>=0.5``.

Advanced usage
--------------
-  **Multiple Inheritance from Abstract Models** - Many Salesforce models use
   the same sets of fields, but using a single inheritance tree would be too
   complicated and fragile. Proxy models and mixins are also supported.

-  **Testing** - By default, tests will be run against the SFDC connection
   specified in settings.py, which will substantially increase testing time.
   
   One way to speed this up is to change the SALESFORCE_DB_ALIAS to point to
   another DB connection (preferably SQLite) during testing using the
   ``TEST_*`` settings variables. Django unit tests without SalesforceModel
   are fast everytimes. Special read only fields that are updated only by SFDC
   e.g. ``last_modified_date`` need more parameters to be possible to save them
   into an alternate database, e.g. by ``auto_now=True`` or to play with
   ``null=True`` or ``default=...``.
   
-  **Multiple SFDC connections** - In most cases, a single connection is all
   that most apps require, so the default DB connection to use for Salesforce
   is defined by the ``SALESFORCE_DB_ALIAS`` settings variable. This behavior
   can be also configured by ``DATABASE_ROUTERS``, replacing the use of
   salesforce.backend.router.ModelRouter.

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

-  **Query deleted objects** - Deleted objects that are in trash bin are
   not selected by a normal queryset, but if a special method ``query_all``
   is used then also deleted objects are searched.
   If a trash bin is supported by the model then a boolean field ``IsDeleted``
   can be in the model and it is possible to select only deleted objects ::

     deleted_list = list(Lead.objects.filter(IsDeleted=True).query_all())

-  **Migrations** - Migrations can be used for an alternate test database
   with SalesforceModel. Then all tables must have Meta ``managed = True`` and
   attributes db_table and db_column are required. (Migrations in SFDC
   will be probably never supported, though it was experimantally tested
   creation of a new simple table in sandbox if a development patch is
   applied and permissions increased. If anything would be implemented after
   all, a new attribute will be added to SalesforceModel for safe forward
   compatibility. Consequently, the setting ``managed = True`` can be considered
   safe as it is related only to the alternate non SFDC database configured
   by ``SF_ALIAS``.)

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
-  **Multiple Deletes** — Multiple delete support is not yet
   implemented.
-  **Database Migrations** — ``migrate`` will only create new tables; in non-SF
   databases (useful for unit tests); SFDC classes are assumed to already
   exist with the appropriate permissions.


Backwards-incompatible changes
------------------------------

-  v0.6.9: This is the last code that supports old Django 1.7 and 1.8.0 - 1.8.3

-  v0.6.1: This is the last code that supports old Django 1.4, 1.5, 1.6.

-  v0.5: The name of primary key is currently ``'id'``. The backward compatible
   behaviour for code created before v0.5 can be reached by settings ``SF_PK='Id'``.


