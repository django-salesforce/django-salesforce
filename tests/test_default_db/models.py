import datetime
import pytz
from django.conf import settings
from salesforce import models, models_extend

tzinfo = pytz.utc if settings.USE_TZ else None


def now_aware_or_naive():
    if settings.USE_TZ:
        return pytz.utc.localize(datetime.datetime.utcnow())
    return datetime.datetime.utcnow()


class Account(models_extend.SalesforceModel):
    name = models.CharField(max_length=255)


class Contact(models_extend.SalesforceModel):
    last_name = models.CharField(max_length=80)
    first_name = models.CharField(max_length=40, blank=True)
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING)

    class Meta:
        db_table = 'Contact'


def get_default_account() -> Account:
    return Account.objects.order_by('pk')[0]


class TryDefaults(models.SalesforceModel):
    # this model doesn't exist in Salesforce, but it should be valid
    # it is only for coverage of code by tests
    example_str = models.CharField(default=models.DefaultedOnCreate('client'), max_length=50)
    example_bool = models.BooleanField(default=models.DefaultedOnCreate(True), db_column='ExampleBool__c')
    example_bool_2 = models.BooleanField(db_column='ExampleBool2__c', default=models.DefaultedOnCreate(False))
    example_bool_3 = models.BooleanField(db_column='ExampleBool3__c', default=models.DEFAULTED_ON_CREATE)
    example_datetime = models.DateTimeField(default=models.DefaultedOnCreate(now_aware_or_naive),
                                            db_column='ExampleDatetime__c')
    example_datetime_2 = models.DateTimeField(
        default=models.DefaultedOnCreate(datetime.datetime(2021, 3, 31, 23, 59, tzinfo=tzinfo)))
    example_date = models.DateField(default=datetime.date.today)
    example_date_2 = models.DateField(default=models.DefaultedOnCreate(datetime.date(2021, 3, 31)))
    example_foreign_key = models.ForeignKey(Account, on_delete=models.DO_NOTHING,
                                            default=models.DefaultedOnCreate(get_default_account))
    example_time = models.TimeField(default=models.DefaultedOnCreate(datetime.time(23, 59)))
