## Welcome to the django-salesforce wiki!

### Field Naming Conventions
In both Django and Salesforce double underscores are significant, so to make custom fields work in Django, be sure to specify the `db_column` argument in the model field definition, i.e.
`Last_Login = models.DateTimeField(db_column='Last_Login__c',max_length=40)`