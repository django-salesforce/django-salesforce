from django.utils.timezone import now
from salesforce import models
from salesforce.models import SalesforceModel


class User(SalesforceModel):  # type: ignore[type-arg]
    name = models.CharField(max_length=80)


class Account(SalesforceModel):  # type: ignore[type-arg]
    name = models.CharField(max_length=80)
    owner = models.ForeignKey(User, on_delete=models.DO_NOTHING, default=models.DEFAULTED_ON_CREATE,)


class Contact(SalesforceModel):  # type: ignore[type-arg]
    last_name = models.CharField(max_length=40)
    donor_class = models.CharField(custom=True, db_column='Donor_class__c', max_length=255, verbose_name='Donor class',
                                   default=models.DefaultedOnCreate('None'), blank=True, null=False)


class Unreal(SalesforceModel):  # type: ignore[type-arg]
    bool_x = models.BooleanField(default=models.DEFAULTED_ON_CREATE)
    int_x = models.IntegerField(default=models.DEFAULTED_ON_CREATE)
    float_x = models.FloatField(default=models.DEFAULTED_ON_CREATE)
    decimal_x = models.DecimalField(default=models.DEFAULTED_ON_CREATE, decimal_places=2, max_digits=9)
    str_x = models.CharField(default=models.DEFAULTED_ON_CREATE, max_length=255)
    date_x = models.DateField(default=models.DEFAULTED_ON_CREATE)
    datetime_x = models.DateTimeField(default=models.DEFAULTED_ON_CREATE)
    time_x = models.TimeField(default=models.DEFAULTED_ON_CREATE)
    str2_x = models.CharField(default=models.DefaultedOnCreate('no'), max_length=255)
    bool2_x = models.BooleanField(default=models.DefaultedOnCreate(True))
    callable_timestamp = models.DateTimeField(default=models.DefaultedOnCreate(now))
    normal = models.CharField(max_length=255)
