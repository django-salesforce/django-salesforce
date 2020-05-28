**Body of Document or Attachment** can be fetched by calling a code with the link that is in the field `body`.
``` python
from django.db import connections

class Attachment(SalesforceModel):
    name = models.CharField(max_length=255, verbose_name='File Name')
    content_type = models.CharField(max_length=120, blank=True, null=True)
    body = models.TextField()

    def fetch_content(self):
        relative_url = self.body
        blob = connections['salesforce'].connection.handle_api_exceptions('GET', relative_url)
        return blob
```