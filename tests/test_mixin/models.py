"""Demonstrate that a Model can inherite from more abstract models."""

from django.conf import settings
import salesforce
from salesforce import models
from salesforce.models import SalesforceModel

# All demo models simplified for readability, except tested features


class User(SalesforceModel):
    username = models.CharField(max_length=80)
    email = models.CharField(max_length=100)


class DefaultMixin(SalesforceModel):
    """Common fields used in the most of SFDC models."""
    last_modified_date = models.DateTimeField(sf_read_only=models.READ_ONLY, auto_now=True)
    owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                              default=models.DEFAULTED_ON_CREATE)  # db_column='OwnerId'

    class Meta:
        abstract = True


class CommonAccount(DefaultMixin, SalesforceModel):
    """Common fields of Salesforce Account model."""
    description = models.TextField()
    phone = models.CharField(max_length=255)

    class Meta:
        abstract = True


class CoreAccount(SalesforceModel):
    """Fields specific to standard Account only."""
    name = models.CharField(max_length=255)

    class Meta:
        abstract = True


class PersonAccount(SalesforceModel):
    """Fields specific to Account after activating "Person Account"."""
    LastName = models.CharField(max_length=80)
    FirstName = models.CharField(max_length=40)
    Name = models.CharField(max_length=255, sf_read_only=models.READ_ONLY)
    IsPersonAccount = models.BooleanField(default=False, sf_read_only=models.READ_ONLY)
    PersonEmail = models.CharField(max_length=100)

    class Meta:
        abstract = True


if not getattr(settings, 'PERSON_ACCOUNT_ACTIVATED', False):
    class Account(CommonAccount, CoreAccount):
        pass
else:
    class Account(CommonAccount, PersonAccount):  # type: ignore[no-redef] # noqa
        pass


class DummyMixin(object):
    def some_overridden_method(self):
        pass


class DummyMixin2(object):
    pass


class Contact(DummyMixin, DefaultMixin, SalesforceModel, DummyMixin2):
    name = models.CharField(max_length=255, sf_read_only=models.READ_ONLY)
    last_name = models.CharField(max_length=80)
    first_name = models.CharField(max_length=40, blank=True)
    account = salesforce.fields.ForeignKey(Account, on_delete=salesforce.models.DO_NOTHING)


class ProxyContact(Contact):
    class Meta:
        proxy = True


class Proxy2Contact(ProxyContact):
    class Meta:
        proxy = True
