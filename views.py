from django import http

from fu_web.salesforce import models

def test(request):
	result = models.Account.objects.filter(active=1)
	return http.HttpResponse(repr(result))