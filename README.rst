django-salesforce
=================

This library allows you to load and edit the objects in any Salesforce instance using Django models. The integration
is fairly complete, and generally seamless for most uses. It works by integrating with the Django ORM, allowing access
to the objects in your SFDC instance as if they were "local" databases.

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


4. **(optional)** To override the default REST timeout of 3 seconds,
   define ``SALESFORCE_QUERY_TIMEOUT`` in your settings file::

    SALESFORCE_QUERY_TIMEOUT = 3

5. **(optional)** If you want to use another name for your Salesforce DB
   connection, define ``SALESFORCE_DB_ALIAS`` in your settings file::

    SALESFORCE_DB_ALIAS = 'salesforce'

6. Add ``salesforce.router.ModelRouter`` to your ``DATABASE_ROUTERS``
   setting::

    DATABASE_ROUTERS = [
        "salesforce.router.ModelRouter" 
	]

7. Define a model that extends ``salesforce.models.SalesforceModel``
8. If you want to use the model in the Django admin interface, use a
   ModelAdmin that extends ``salesforce.admin.RoutedModelAdmin``
9. You're all done! Just use your model like a normal Django model.

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
-  **Multiple Salesforce Connections** — Creating more than one salesforce
   connection entry in ``DATABASES`` will probably fail in unpredictable ways. ``;-)``
-  **Multiple Updates** — Multiple update support is not yet
   implemented.
-  **Multiple Deletes** — Multiple delete support is not yet
   implemented.
-  **Database Sync** — There is no plan to support DB creation for the
   forseeable future.
