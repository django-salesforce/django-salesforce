"""Backward compatible behaviour with primary key 'Id' and upper-case field names"""

import datetime
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


class TryDefaults(SalesforceModel):
    # this model doesn't exist in Salesforce, but it should be valid
    # it is only for coverage of code by tests
    example_str = models.CharField(max_length=50, default=models.DefaultedOnCreate('client'))
    example_datetime = models.DateTimeField(default=models.DefaultedOnCreate(datetime.datetime(2021, 3, 31, 23, 59)))
    # example_date = models.DateTimeField(default=models.DefaultedOnCreate(datetime.date(2021, 3, 31)))
    example_time = models.DateTimeField(default=models.DefaultedOnCreate(datetime.time(23, 59)))
    example_foreign_key = models.ForeignKey(User, on_delete=models.DO_NOTHING, default=models.DefaultedOnCreate())
    # ,default=models.DefaultedOnCreate(User(pk='000000000000000')))
    example_bool = models.BooleanField(default=models.DefaultedOnCreate(True))
    example_bool_2 = models.BooleanField(default=models.DefaultedOnCreate(False))
