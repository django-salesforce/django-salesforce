# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

import logging

from django.conf import settings
from django import template, shortcuts, http

from salesforce.testrunner.example import models, forms

log = logging.getLogger(__name__)

def list_accounts(request):
	accounts = models.Account.objects.all()[0:5]
	
	return shortcuts.render_to_response('list-accounts.html', dict(
		title           = "List First 5 Accounts",
		accounts        = accounts,
	), context_instance=template.RequestContext(request))

def search_accounts(request):
	accounts = []
	if(request.method == 'POST'):
		form = forms.SearchForm(request.POST)
		if(form.is_valid()):
			accounts = models.Account.objects.filter(Name__icontains=form.cleaned_data['query'])
	else:
		form = forms.SearchForm()
		
	return shortcuts.render_to_response('search-accounts.html', dict(
		title           = "Search Accounts by Email",
		accounts        = accounts,
		form            = form,
	), context_instance=template.RequestContext(request))
