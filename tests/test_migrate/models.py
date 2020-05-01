"""Backward compatible behaviour with primary key 'Id' and upper-case field names"""

from salesforce import models
from salesforce.models import SalesforceModel


class User(SalesforceModel):
    username = models.CharField(max_length=80)
    email = models.CharField(max_length=100)
    last_name = models.CharField(max_length=80)
    first_name = models.CharField(max_length=40, null=True, blank=True)
    is_active = models.BooleanField(default=False)


class Lead(SalesforceModel):
    company = models.CharField(max_length=255)
    last_name = models.CharField(max_length=80)

    class Meta:
        db_table = 'Lead'


class Contact(SalesforceModel):
    last_name = models.CharField(max_length=80)
    owner = models.ForeignKey(User, on_delete=models.DO_NOTHING, default=models.DefaultedOnCreate(User))

    class Meta:
        managed = True
        db_table = 'Contact'
