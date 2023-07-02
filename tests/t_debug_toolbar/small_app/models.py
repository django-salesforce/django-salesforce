from salesforce import models


class Lead(models.SalesforceModel):
    LastName = models.CharField(max_length=80)
    Name = models.CharField(max_length=121, sf_read_only=models.READ_ONLY)
    Company = models.CharField(max_length=255)
    Status = models.CharField(max_length=100, default='Open')

    def __str__(self):
        return self.Name
