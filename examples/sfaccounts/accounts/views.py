# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

from django.conf import settings
from django import template, shortcuts, http

def list_accounts(request):
	import django_roa
	from salesforce.backend import manager
	if(django_roa.Manager != manager.SalesforceManager):
		django_roa.Manager = manager.SalesforceManager
	
	from salesforce import models
	
	return shortcuts.render_to_response('list-accounts.html', dict(
		title           = "Password Reset",
		accounts        = models.Account.objects.all()[0:5],
	), context_instance=template.RequestContext(request))
