from salesforce import models


class Contact(models.SalesforceModel):
    last_name = models.CharField(max_length=80)
    # a field that is not used in example.Contact
    title = models.CharField(max_length=40, blank=True, null=True)

    class Meta(models.Model.Meta):
        db_table = 'Contact'
        verbose_name = 'Contact'
        verbose_name_plural = 'Contacts'
        app_label = 'test_salesforce'
