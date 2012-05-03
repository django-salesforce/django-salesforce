from django import http

from fu_web.salesforce import authenticate, models

def test(request):
	return http.HttpResponse(authenticate())