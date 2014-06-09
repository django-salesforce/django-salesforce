django-salesforce
=================

.. image:: https://travis-ci.org/freelancersunion/django-salesforce.svg?branch=master
   :target: https://travis-ci.org/freelancersunion/django-salesforce

This library allows you to load and edit the objects in any Salesforce instance using Django models. The integration
is fairly complete, and generally seamless for most uses. It works by integrating with the Django ORM, allowing access
to the objects in your SFDC instance as if they were "local" databases.

Python 2.6, 2.7, 3.3, 3.4 or pypy; Django 1.4.2 - 1.7 (but Django 1.4 can't be combined with Python 3)

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

8. If you want to use the model in the Django admin interface, use a
   ModelAdmin that extends ``salesforce.admin.RoutedModelAdmin``

9. You're all done! Just use your model like a normal Django model.

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

-  **Testing** You can set ``SALESFORCE_DB_ALIAS = 'default'`` if you want to
   run your unit tests fast in memory with the sqlite3 driver, without access
   to the SF database. (Only login server is accessed but not the data server.)
-  **Multiple databases** of similar structure can be used with the SF model,
   including more SF databases. If ``SALESFORCE_DB_ALIAS`` is set to a non SF
   database, than tables defined by SF model can be created by syncdb in that
   database if a model has a ``Meta`` class with the attribute ``managed=True``
   or undefined. This behaviour can be also configured by ``DATABASE_ROUTERS``.
-  **Non SF databases** If an inner ``Meta`` class is used, e.g. for a
   ``db_table`` option of custom SF object for a name that ends with ``__c``,
   then that Meta must be a descendant of ``SalesforceModel.Meta`` or must have
   the attribute ``managed=False``.
-  **Custom Managers** Custom managers of a model must be descendants of
   ``salesforce.manager.SalesforceManager``.
   Switching the type by ``SALESFORCE_DB_ALIAS`` is easy, e.g. for fast tests.
   If SF non SF databases should be used for SF models together, switched by
   ``.using(alias).``, you shall switch it by ``.db_manager(alias)`` instead.
   e.g. ``Contact.objects.db_manager(alias).my_manager(params...)``

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
-  **Custom Object Names** — Custom Salesforce tables and columns (and a
   couple of other SF concepts) are indicated with a double-underscore in
   the name, and will need to have their Django field name overridden
   (using 'db\_column'), so as not to interfere with the double-underscore
   syntax used in Django query filters.
-  **Inheritence** — All models for object types on Salesforce must
   extend salesforce.models.SalesforceModel. The model router checks for
   this to determine which models to handle through the Salesforce
   connection.
-  **Multiple Updates** — Multiple update support is not yet
   implemented.
-  **Multiple Deletes** — Multiple delete support is not yet
   implemented.
-  **Database Sync** — There is no plan to support DB creation for the
   forseeable future.
