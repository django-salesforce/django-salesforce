from __future__ import unicode_literals
from salesforce import models

from tests.inspectdb import models as models_template

class User(models.Model):
    Username = models.CharField(max_length=80)

class Organization(models.Model):
    # all fields are copie dynamically
    class Meta:
        db_table = 'Organization'
        dynamic_field_patterns = models_template, ['.*']
