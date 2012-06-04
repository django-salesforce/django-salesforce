django-salesforce
=================

Salesforce backend for Django&#39;s ORM.

Quick Start
-----------

1. Install django-salesforce:
   `pip install django-salesforce`

2. Add the `salesforce` app to your `INSTALLED_APPS` setting
3. Add a salesforce connection to your `DATABASES` setting
```yaml
    'salesforce': {
        'ENGINE': 'salesforce.backend',
        "CONSUMER_KEY" : '',
        "CONSUMER_SECRET" : '',
        'USER': '',
        'PASSWORD': '',
        'HOST': 'https://test.salesforce.com',
    }
```

4. **(optional)** If you want to use another name for your Salesforce DB connection, define `SALESFORCE_DB_ALIAS` in your settings file.

5. Add `salesforce.router.ModelRouter` to your `DATABASE_ROUTERS` setting
```yaml
    DATABASE_ROUTERS = [
        "salesforce.router.ModelRouter"
    ]
```

6. Define a model that extends `salesforce.models.SalesforceModel`
7. If you want to use the model in the Django admin interface, use a ModelAdmin that extends `salesforce.admin.RoutedModelAdmin`
8. You're all done! Just use your model like a normal Django model.

Caveats
-------
This package is in continuous development, and the ultimate goal is to support all reasonable
features of the Salesforce platform, but for now here are the potential pitfalls and unimplemented
operations:

* **Large Objects** — Since the entire result set needs to be transferred over HTTP, and since Salesforce tends to
    use extremely long column counts in their tables, it's assumed that users will create Django-Salesforce models
    that are specific to the individual app needs. Models with this library are for example and documentation purposes.
* **Custom Object Names** — Custom Salesforce tables and columns (and a couple other SF concepts) are indicated
    with a double-underscore in the name, and will need to have their Django field name overridden (with 'db_column'),
    so to not interfere with the double-underscore syntax used in Django query filters.
* **Inheritence** — All models for object types on Salesforce must extend salesforce.models.SalesforceModel. The model
    router checks for this to determine which models to handle through the Salesforce connection.
* **Multiple Updates** — Multiple update support is not yet implemented.
* **Multiple Deletes** — Multiple delete support is not yet implemented.
* **Foreign Keys** — Foreign key support is not yet implemented.
* **Database Sync** — There is no plan to support DB creation for the forseeable future.