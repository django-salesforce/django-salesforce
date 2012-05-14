# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

import logging

from django.conf import settings
from django import template, shortcuts, http

log = logging.getLogger(__name__)

def list_accounts(request):
	from salesforce import models
	accounts = models.Account.objects.all()[0:5]
	
	print accounts
	
	return shortcuts.render_to_response('list-accounts.html', dict(
		title           = "Password Reset",
		accounts        = accounts,
	), context_instance=template.RequestContext(request))
