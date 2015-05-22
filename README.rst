django-salesforce
=================

.. image:: https://travis-ci.org/django-salesforce/django-salesforce.svg?branch=master
   :target: https://travis-ci.org/django-salesforce/django-salesforce

This library allows you to load and edit the objects in any Salesforce instance
using Django models. The integration is fairly complete, and generally seamless
for most uses. It works by integrating with the Django ORM, allowing access to
the objects in your SFDC instance as if they were in a traditional database.

Python 2.6, 2.7, 3.3, 3.4 or pypy; Django 1.4.2 - 1.7, partly Django 1.8.
The best supported version is currently Django 1.7, including relative
complicated subqueries. Django 1.8 is only very rudimentally supported, without
raw queries and without values_list() and values() methods. The usual support
can be expected in the next django-salesforce version.
Note that Django 1.4.x is not compatible with Python 3.

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
   * ``HOST`` is ``https://test.salesforce.com`` to access the sandbox, or
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

7. Define a model that extends ``salesforce.models.Model`` or export the
   complete SF schema by ``python manage.py inspectdb --database=salesforce``
   and simplify it to what you need.

8. You're all done! Just use your model like a normal Django model.

9. (Optional) Create a normal Django admin.py module for your Salesforce model.

Primary Key
-----------
Salesforce doesn't allow you to define custom primary keys, so django-salesforce
will add them automatically in all cases. You can override capitalization and use
primary key `id` by configuring `SF_PK='id'` in your project settings. The previous
capitalization of `Id` is only for old projects, but it will stay as the default
variant until `django-salesforce>=0.5`.

Foreign Key Support
-------------------

**Foreign key filters** are currently possible only from child to parent with some
restrictions:

They are fully supported with Django 1.7+ without other restrictions. **New**

With Django 1.6 and older, ForeignKey filters are  possible only for the first level of
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
type is supported::

    note = Note.objects.filter(parent_type='Contact')[0]
    parent_model = getattr(example.models, note.parent_type)
    parent_object = parent_model.objects.get(pk=note.parent_id)
    assert note.parent_type == 'Contact'

Example of `Note` model is in `salesforce.testrunner.example.models.Note`.

Advanced usage
--------------
-  **Multiple Inheritance from Abstract Models** - Many Salesforce models use
   the same sets of fields, but using a single inheritance tree would be too
   complicated and fragile. Proxy models and mixins are also supported.

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

Introspection and special attributes of fields
----------------------------------------------
Some Salesforce fields can not be fully used without special attributes. You
can see in the output of ``inspectdb`` in the most complete form.

-  **sf_read_only** - Some fields require this special attributes to make the
   model writable. Some fields are completely read only (``READ_ONLY``)
   or insertable only but can not be later updated (``NOT_UPDATEABLE``) or
   updateable only but can not be specified on insert (``NOT_CREATEABLE``).
   Examples of such fields are automatically updated fields "last_modified_by" and
   "last_modified_date" or fields defined by a formula like "name" of contact,
   given by "first_name" and "last_name". Example::

   last_modified_date = models.DateTimeField(sf_read_only=models.READ_ONLY)

-  **Defaulted on create** - Some fields have a dynamic default value unknown
   by Django and assigned by Salesforce if the field is omitted when a new object
   is inserted. This rule will not be used if the value is ``None``.
   Sometimes is ``None`` even not accepted by Salesforce, while the missing
   value is ok. Django-salesforce supports it by a special default value
   ``model.BooleanField(default=models.DEFAULTED_ON_CREATE)``. That means "let
   it to Salesforce". This is useful for all fields marked by attribute
   ``defaultedOnCreate`` in Salesforce. For example the current user of
   Salesforce is assigned to ``owner`` field if no concrete user is  assigned,
   but None would be rejected. All boolean fields have different default values
   according to current ``Checked/Unchecked`` preferences.

-  **Comments # Reference to tables [...]**
   Some builtin foreign keys are references to more tables. The class of first
   table is used in the exported ``ForeignKey`` and all tables are listed in
   the comment. Any of them can be used instead.::
   models.ForeignKey(User) # Reference to tables [SelfServiceUser, User]
   cl object  [SelfServiceUser, User]

-  **Partial Database Introspection with inspectdb** Tables that are exported into a
   Python model can be restricted by regular expression::

     python manage.py inspectdb --table-filter="Contact$|Account" --database=salesforce

   In this example, inspectdb will only export models for tables with exact
   name ``Contact`` and all tables that are prefixed with ``Account``. This
   filter works with all supported database types.

-  **Accessing the Salesforce SOAP API** - There are some Salesforce actions that cannot or can hardly
   be implemented using the generic relational database abstraction and the REST API.
   For some of these actions there is an available endpoint in the old Salesforce API
   (SOAP) that can be accessed using our utility module. In order to use that module,
   you will need to install an additional dependency ::

     pip install beatbox

   Here is an example of usage with ``Lead`` conversion ::

     from salesforce.utils import convert_lead

     lead = Lead.objects.all()[0]
     response = convert_lead(lead)

   For the particular case of ``Lead`` conversion, beware that having
   some *custom* and *required* fields in either ``Contact``,
   ``Account`` or ``Opportunity`` is not supported. This arises from
   the fact that the conversion mechanism on the Salesforce side is only
   meant to deal with standard Salesforce fields, so it does not really
   care about populating custom fields at insert time.

   One workaround is to map a custom required field in
   your `Lead` object a custom required field in target objects
   (i.e., `Contact`, `Opportunity` or `Account`) or to garantee that
   a suitable value is set by your application to the source Lead field,
   at least just before the conversion. Follow the
   `instructions <http://www.python.org/https://help.salesforce.com/apex/HTViewHelpDoc?id=customize_mapleads.htm>`__
   for more details.

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

-  If you use multiple Salesforce databases or multiple instances of AdminSite, you'll
   probably want to extend ``salesforce.admin.RoutedModelAdmin``" in your admin.py

-  **Dynamic authorization** - The original use-case for django-salesforce assumed
   use of a single set of credentials with read-write access to all necessary objects.
   It's now possible to write applications that use OAuth to interact with a Salesforce
   instance's data on your end user's behalf. You simply need to know or request the 
   `Access Token <https://www.salesforce.com/us/developer/docs/api_rest/Content/quickstart_oauth.htm>`
   for the user in question. In this situation, it's not necessary to save any credentials
   for SFDC in Django settings. The manner in which you request or transmit this token
   (e.g., in the `Authorization:` header) is left up to the developer at this time.

   Configure your ``DATABASES`` setting as follows::

    'salesforce': {
        'ENGINE': 'salesforce.backend',
        'HOST': 'https://your-site.salesforce.com',
        'CONSUMER_KEY': '.',
        'CONSUMER_SECRET': '.',
        'USER': 'dynamic auth',
        'PASSWORD': '.',
    }

   A static SFDC connection can be specified with the data server URL in "HOST"
   Note that in this case we're not using the URL of the login server — the data
   server URL can be also used for login.
   
   Items with `'.'` value are ignored when using dynamic auth, but cannot be left
   empty.

   The last step is to enable the feature in your project in some way, probably by
   creating a Django middleware component. Then at the beginning of each request::

      from django.db import connections
      # After you get the access token for the user in some way
      # authenticate to SFDC with
      connections['salesforce'].sf_session.auth.dynamic_start(access_token)
      
      # or to override the `instance_url` on a per-request basis
      connections['salesforce'].sf_session.auth.dynamic_start(access_token, instance_url)

   Make sure to purge the access token at end of request::

        connections['salesforce'].sf_session.auth.dynamic_end()

   You can continue to supply static credentials in your project settings, but they will
   only be used before calling dynamic_start() and/or after calling dynamic_end().

Backwards-incompatible changes
------------------------------

-  The name of primary key is currently `id`. The backward compatible behaviour
   can be reached by settings `SF_PK='Id'`.

News since version 0.5
----------------------

-  All child to parent filters are still correctly supported for Django 1.7 in
   many levels, including foreign keys between custom models or mixed builtin
   and custom models, also filters where the same model is used multiple times,
   e.g. filter Account objects by a field of their parent Account.
