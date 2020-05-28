## Django-salesforce

### Wiki Contents

- [Documents and Attachments](Documents-and-Attachments) - How to get binary blob data
- [Empty strings in .filter() and .exclude()](Empty-strings-in-filters) - How to exclude empty strings in queries etc.
- [Error messages](Error-messages) - How to understand some strange error messages
- [Experimental Features](Experimental-Features) - dynamic authentization, multiple SF databases with Admin
- [Foreign Key Support](Foreign-Key-Support) - queries based on fields of related tables, Many2Many relationships
- [Introspection and Special Attributes of Fields](Introspection-and-Special-Attributes-of-Fields) - How to understand the database model exported by inspectdb and how to exactly describe Salesforce by the the model.
- [SalesforceModels used with local databases](SalesforceModels-used-with-local-databases)

### Useful issues links
- [Tuning REQUESTS_MAX_RETRIES](https://github.com/django-salesforce/django-salesforce/issues/159) - A variable used in edge-cases that is difficult to describe, see this issue for more info.
- [Converting Leads](../Lead-Conversion) - Converting leads is not directly supported by the Salesforce REST interface, but an included helper function can use beatbox and the SOAP interface.

---
### Short notes

#### Field Naming Conventions
In both Django and Salesforce double underscores are significant for different purposes, so to make custom fields work in Django, be sure to specify the `db_column` argument in the model field definition, i.e.:  
`Last_Login = models.DateTimeField(db_column='Last_Login__c', max_length=40)`  
It is automatic in models created by inspectdb.

#### Faster migrations and tests
Every run of `makemigrations` requires a login to the database. It significantly slower for Salesforce than for a local database, even for small models, but this time fortunately will now grow. The tests can slow down with Django, if the `default` database has many migrations and some are applied and complex models for `salesforce` database are used, e.g. hundreds kB exported by inspectdb without pruning (`makemigrations`  `names of used tables` or  `--table-filter=table_filter_regexp` `...`). Many other general workarounds are described on the Internet for Django, e.g. merging of old migrations. It is also possible to use an option `'MIGRATE': False` in Django 3.1 to skip migrations in tests even if migrations files exist:
`DATABASES['salesforce']['TESTS'] = {'MIGRATE': False, 'DEPENDENCIES': []}`