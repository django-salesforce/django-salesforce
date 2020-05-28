"""Backward compatible behaviour with primary key 'Id' and upper-case field names"""

from salesforce import models
from salesforce.models import SalesforceModel


class User(SalesforceModel):
    Username = models.CharField(max_length=80)
    Email = models.CharField(max_length=100)


class Lead(SalesforceModel):
    Company = models.CharField(max_length=255)
    LastName = models.CharField(max_length=80)
    Owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                              default=models.DEFAULTED_ON_CREATE, db_column='OwnerId')


# models for unit tests used without a connection only

class A(SalesforceModel):
    email = models.EmailField(custom=True)

    class Meta:
        db_table = 'A__c'


class B(SalesforceModel):

    class Meta:
        db_table = 'B__c'


class AtoB(SalesforceModel):
    a = models.ForeignKey(A, models.DO_NOTHING, custom=True)
    b = models.ForeignKey(B, models.DO_NOTHING, custom=True)

    class Meta:
        db_table = 'AtoB__c'
