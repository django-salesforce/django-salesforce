Help for some Error Messages
----------------------------

**Q:** `"...Error: Table 'my_sfdc_application.SomeTable' doesn't exist"` is reported on a line in program file like "...sqlite...", "...postgres..." or "...mysql...".

* Missed to set `DATABASE_ROUTERS = ["salesforce.router.ModelRouter"]` in your `settings.py` and therefore the "default" database is used instead of "salesforce"
* Missed to use the base class `salesforce.models.Model` instead of `django.db.models.Model` in that your model class.  
  
  
**Q:** `SalesforceError: {'errorCode': 'INVALID_TYPE', 'message': "... FROM SomeSObject ...`  
  `sObject type 'SomeSObject' is not supported. ..."`

* Typo in the `db_table` name that doesn't equal to object's `API Name` in Salesforce (e.g. missing "__c").  
* The current user's permissions are insufficient for this sObject type. Some fields created by installed packages or by API calls can be set without permissions even for the System Administrator profile if he doesn't add permission himself.