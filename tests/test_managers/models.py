"""Backward compatible behaviour with primary key 'Id' and upper-case field names"""

from salesforce import models
from salesforce.models import SalesforceModel
from salesforce.backend.manager import SalesforceManager
from salesforce.backend.query import SalesforceQuerySet


class ContactQuerySet(SalesforceQuerySet):
    def people(self):
        return self.filter(account__name__gt='A')


class FilteredManager(SalesforceManager):
    def get_queryset(self):
        return ContactQuerySet(self.model, using=self._db).people()

    def people(self):
        return self.get_queryset().people()


class Account(SalesforceModel):
    name = models.CharField(max_length=80)


class Contact(SalesforceModel):
    last_name = models.CharField(max_length=80)
    account = models.ForeignKey(Account, models.DO_NOTHING)
    objects = FilteredManager()
