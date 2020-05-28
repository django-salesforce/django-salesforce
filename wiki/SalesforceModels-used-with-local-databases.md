It is possible to use a Salesforce Model with a local 'default' database

1. to run tests that don't require special Salesforce features
2. to permanently save objects or even to copy objects between the local and cloud databases

If SalesforceModels tables should be created in a local ('default') database then it should be configured in settings at the time when running `migrate` or when running `test`, even without migrations:  
`SALESFORCE_DB_ALIAS = 'default'`

If both databases should cooperate as transparently as possible then a module `salesforce.models_extend` should be used instead of `salesforce.models` by changing one line in your models.py. e.g. `from salesforce import models_extend as models` or by adding `from salesforce.models_extend import SalesforceModel`.  
It uses a string primary key on local databases and random uuid value if the instance with empty primary key is saved to the local database. (The primary key generator can be configured in settings by `SF_ALT_PK`. The default is `uuid.uuid4().hex`) 

Restrictions:
- It is not possible to use `default=DefaultedOnCreate(...)` on some field types with a local database. It works on boolean and numeric types, but it is not possible on CharField or ForeignKey if empty values are not allowed (`null=False`).
- It is not possible to create migrations with a default value on a ForeignKey. That is especially useful for an `owner` field.

Possible solutions:
* Replace `default=DefaultedOnCreate(...)` by a normal default value of by a callable that assigns an appropriate value in Django at run-time when the instance is created, not only in cloud when the instance is saved.
 ofare to remove a ForeignKey and to set a real value in user code or 
* In a special case if that field is used only for reading it can be configured as a read only field (`sf_read_only=models.READ_ONLY`) or maybe the field is not necessary at all.

- The normal primary key in local databases is with integer values.