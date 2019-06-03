from salesforce import models


class Account(models.SalesforceModel):
    name = models.CharField(max_length=255)


class Contact(models.SalesforceModel):
    last_name = models.CharField(max_length=80)
    first_name = models.CharField(max_length=40, blank=True)
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING)

    class Meta:
        db_table = 'Contact'
