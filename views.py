from django import http

from fu_web.salesforce import authenticate, models

def test(request):
	result = models.Account.objects.all()
	return http.HttpResponse(result)