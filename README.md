django-salesforce
=================

Salesforce backend for Django&#39;s ORM.

Quick Start
-----------

1. Install django-salesforce:

   `pip install django-salesforce`

2. Add the `salesforce` app to your `INSTALLED_APPS` setting
3. Configure your Salesforce API connection:

	'salesforce': {
	    'ENGINE': 'salesforce.backend',
	    "CONSUMER_KEY" : '',
	    "CONSUMER_SECRET" : '',
	    'USER': '',
	    'PASSWORD': '',
	    'HOST': 'https://test.salesforce.com',
	}

4. Add `salesforce.router.ModelRouter` to your `DATABASE_ROUTERS` setting

	DATABASE_ROUTERS = [
	    "salesforce.router.ModelRouter"
	]

5. Define a model that extends `salesforce.models.SalesforceModel`
6. If you want to use the model in the Django admin interface, use a ModelAdmin that extends `salesforce.admin.RoutedModelAdmin`