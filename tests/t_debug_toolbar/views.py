from django.http import HttpResponse
from salesforce.backend.test_helpers import current_user
from salesforce.testrunner.example import models


def account_insert_delete(request):
    # simple test view for debug-toolbar
    user = models.User.objects.get(Username=current_user)
    account = models.Account(Name='abc', Owner=user)
    account.save()
    account.Name = 'xyz'
    account.save()
    account.delete()
    return HttpResponse('<html><body>OK</body></html>')
