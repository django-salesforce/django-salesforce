from salesforce import models

from tests.inspectdb.dependent_model import models_template


class User(models.Model):
    Username = models.CharField(max_length=80)


class Organization(models.Model):
    # all fields are copied dynamically
    class Meta:
        db_table = 'Organization'
        dynamic_field_patterns = models_template, ['.*']
