from django.http import HttpResponse
from salesforce.testrunner.example import models


def account_insert_delete(request):
    # simple test view for debug-toolbar
    account = models.Account(Name='abc')
    account.save()
    account.Name = 'xyz'
    account.save()
    account.delete()
    return HttpResponse('<html><body>OK</body></html>')
