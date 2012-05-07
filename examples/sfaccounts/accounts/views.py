# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

from django.conf import settings
from django import template, shortcuts, http

from salesforce import models

def list_accounts(request):
	return shortcuts.render_to_response('list-accounts.html', dict(
		title           = "Password Reset",
		accounts        = models.Account.objects.all()[0:5],
	), context_instance=template.RequestContext(request))
