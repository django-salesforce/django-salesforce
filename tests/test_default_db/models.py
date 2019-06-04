from salesforce import models, models_extend


class Account(models_extend.SalesforceModel):
    name = models.CharField(max_length=255)


class Contact(models_extend.SalesforceModel):
    last_name = models.CharField(max_length=80)
    first_name = models.CharField(max_length=40, blank=True)
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING)

    class Meta:
        db_table = 'Contact'
