"""This is a part of an automatically exported database schema ('inspectdb')

Shortened due to readability:
removed very long choices, removed many long fields, reformated long
lines, but still an example of a long model exported from Salesforce.
"""
from salesforce import models_template as models


class User(models.Model):
    Username = models.CharField(max_length=80)
    Email = models.CharField(max_length=100)
    LastName = models.CharField(max_length=80)
    FirstName = models.CharField(max_length=40)


class Organization(models.Model):
    name = models.CharField(max_length=80, sf_read_only=models.NOT_CREATEABLE)
    division = models.CharField(max_length=80, sf_read_only=models.NOT_CREATEABLE, blank=True)
    street = models.TextField(sf_read_only=models.NOT_CREATEABLE, blank=True)
    city = models.CharField(max_length=40, sf_read_only=models.NOT_CREATEABLE, blank=True)
    country = models.CharField(max_length=80, sf_read_only=models.READ_ONLY, blank=True)
    address = models.TextField(sf_read_only=models.READ_ONLY, blank=True)  # This field type is a guess.
    phone = models.CharField(max_length=40, sf_read_only=models.NOT_CREATEABLE, blank=True)
    instance_name = models.CharField(max_length=5, sf_read_only=models.READ_ONLY, blank=True)
    is_sandbox = models.BooleanField(sf_read_only=models.READ_ONLY)
    created_date = models.DateTimeField(sf_read_only=models.READ_ONLY)
    created_by = models.ForeignKey(User, related_name='organization_createdby_set',
                                   sf_read_only=models.READ_ONLY, on_delete=models.DO_NOTHING)
    last_modified_date = models.DateTimeField(sf_read_only=models.READ_ONLY)
    last_modified_by = models.ForeignKey('User', related_name='organization_lastmodifiedby_set',
                                         sf_read_only=models.READ_ONLY, on_delete=models.DO_NOTHING)

    class Meta(models.Model.Meta):
        db_table = 'Organization'
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'
        # keyPrefix = '00D'
