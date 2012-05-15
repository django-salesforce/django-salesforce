django-salesforce
=================

Salesforce backend for Django&#39;s ORM.

Quick Start
-----------

1. Install django-salesforce:

   `pip install django-salesforce`

2. Add the `salesforce` app to your `INSTALLED_APPS` setting
3. Add a salesforce connection to your `DATABASES` setting

    `'salesforce': {
        'ENGINE': 'salesforce.backend',
        "CONSUMER_KEY" : '',
        "CONSUMER_SECRET" : '',
        'USER': '',
        'PASSWORD': '',
        'HOST': 'https://test.salesforce.com',
    }`

4. **(optional)** If you want to use another name for your Salesforce DB connection, define `SALESFORCE_DB_ALIAS` in your settings file.

5. Add `salesforce.router.ModelRouter` to your `DATABASE_ROUTERS` setting

    `DATABASE_ROUTERS = [
        "salesforce.router.ModelRouter"
    ]`

6. Define a model that extends `salesforce.models.SalesforceModel`
7. If you want to use the model in the Django admin interface, use a ModelAdmin that extends `salesforce.admin.RoutedModelAdmin`
8. You're all done! Just use your model like a normal Django model.