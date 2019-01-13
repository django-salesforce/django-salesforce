"""Backward compatible behaviour with primary key 'Id' and upper-case field names"""

from salesforce import models
from salesforce.models import SalesforceModel


class Lead(SalesforceModel):
    company = models.CharField(max_length=255)
    last_name = models.CharField(max_length=80)

    class Meta:
        db_table = 'Lead'


class Contact(SalesforceModel):
    last_name = models.CharField(max_length=80)

    class Meta:
        managed = True
        db_table = 'Contact'
