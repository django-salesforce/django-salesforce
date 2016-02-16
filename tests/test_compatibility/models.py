"""Backward compatible behaviour with primary key 'Id' and upper-case field names"""

from django.conf import settings
import salesforce
from salesforce import models
from salesforce.models import SalesforceModel

class User(SalesforceModel):
    Username = models.CharField(max_length=80)
    Email = models.CharField(max_length=100)

class Lead(SalesforceModel):
    Company = models.CharField(max_length=255)
    LastName = models.CharField(max_length=80)
    Owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
            default=lambda:User(Id='DEFAULT'), db_column='OwnerId')
