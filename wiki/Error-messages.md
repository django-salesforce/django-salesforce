Help for some Error Messages
----------------------------

Many Salesforce error messages are fortunately clear enough or well explained in [SOAP API docs](https://developer.salesforce.com/docs/atlas.en-us.api.meta/api/sforce_api_calls_concepts_core_data_objects.htm#exception_code_topic) (the same messages are declared in the *Partner WSDL*) and they are useful also for REST API. Error messages created by django-salesforce are also easy, thanks to open source that they can be easier fixed.

The following messages on the boundary between SFDC and the framework can be surprising:

**Q:** `"...Error:`**`Table`**`'my_sfdc_application.SomeTable'`**`doesn't exist"`** is reported with a **dot before table name** in a different driver like "...sqlite...", "...postgres..." or "...mysql..." and the error is not a SalesforceError.

* Missed to set `DATABASE_ROUTERS = ["salesforce.router.ModelRouter"]` in your `settings.py` and therefore the "default" database is used instead of "salesforce"
* Missed to use the base class `salesforce.models.Model` instead of `django.db.models.Model` in that your model class.  
  
  
**Q:** `SalesforceError: `**`INVALID_TYPE`**  
&nbsp; &nbsp; &nbsp; &nbsp; ` ...`**`FROM`**` SomeSObject ...`  
&nbsp; &nbsp; &nbsp; &nbsp; ` sObject type 'SomeSObject' is not supported. ..."`

* Typo in the `db_table` name that doesn't equal to object's `API Name` in Salesforce (e.g. missing "__c").  
* The current user's permissions are insufficient for this sObject type. Some fields created by installed packages or by API calls can be set without permissions even for the System Administrator profile if he doesn't add permission himself.

**Q:** `SalesforceError: `**`INVALID_OPERATION_WITH_EXPIRED_PASSWORD`**  
&nbsp; &nbsp; &nbsp; &nbsp; ` The users password has expired, you must call SetPassword before attempting any other API operations`

* The message is clear - **change the password now**. If you use the Django service with a fixed user and password authentication, consider to set a separate user profile for that user with a password policy that never expires.
Setup / Administer / Manage users / Profiles,
Select the current user profile, click "Clone" (new name), to be cloned, click "Password Policies", edit "User passwords expire in" - "never expires". Assign the profile.

**Q:** `LokupError: {"error": "unknown_error", "error_description": "retry your request"}` or a similar `SalesforceAuthError` in django-salesforce 0.9.alpha+.

* Authentication errors were very cryptic (are still?). This error message was also possible if the client did not support a required TLS 1.1+ version.

**Q:** **Foreign languages terms** in the error message  
Some parts of error messages are translated to end user languages by SFDC if the database is configured with a dynamic authentization by end user's Oauth token. The following example message is a case that a Spanish end user doesn't have permission to create a Campaign because a checkbox "Marketing User" is not check in her user configuration.  
`SalesforceError: CANNOT_INSERT_UPDATE_ACTIVATE_ENTITY` / ` entity type cannot be inserted: Campaña`  
Campaign = Campaña (Spanish) (This could be eventually fixed by adding some context from Django to error messages, but it will be redundant for English that is much more frequent language for a database connection user.)

**Q:** `ImproperlyConfigured: Application labels aren't unique, duplicates: salesforce`  
in Django registry if `django-allauth` is installed.

This can be very easily fixed with django-salesforce >= 1.0 by writing `'salesforce.auth.SalesforceDb'` to `INSTALLED_APPS` instead of simple `'salesforce'` or by instructions in issue #212. (The conflict of django-allauth against many packages is a frequent issue, not specific to Salesforce.)

<h4>Q: AssertionError: Too complicated queryset.update()</h4>

`AssertionError: Too complicated queryset.update(). Rewrite it by two querysets. See the wiki about errors`

More complicated queries with related tables are supported only by evaluating the queryset before applying `.update()` or `.delete()` methods.

Instead of `complicated_queryset.update(field_1=value1,...)`  
use a more verbosely  
`TheModel.objects.filter(pk__in=list(complicated_queryset)).update(...)`  
This is because you should check this queryset query or queryset results in development once e.g. check the length of result that it contains not too much or too few rows or check the compiled `where` condition by `print(str(complicated_queryset.values('pk').query))`. (Problematic expressions could be only joins with related tables and added or missing or misplaced `!= NULL` that could be over-optimized by Django.) Two requests used by these two commands are equally effective as `queryset.update()` because Salesforce requires first to get an exact list or primary keys of rows that should be updated or deleted.