from salesforce import models


class Case(models.Model):
    subject = models.CharField(db_column='Subject', max_length=255, blank=True, null=True)
    status = models.CharField(db_column='Status', max_length=255, default='New', blank=True, null=True,
                              choices=[('On Hold', 'On Hold'), ('Closed', 'Closed'), ('New', 'New')])
    origin = models.CharField(db_column='Origin', max_length=255, verbose_name='Case Origin', blank=True, null=True,
                              choices=[('Email', 'Email'), ('Phone', 'Phone'), ('Web', 'Web')])

    class Meta(models.Model.Meta):
        db_table = 'Case'
