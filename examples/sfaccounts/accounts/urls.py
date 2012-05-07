# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

from django.conf.urls.defaults import patterns, url, include

urlpatterns = patterns('sfaccounts.accounts.views',
	url(r'^$', 'list_accounts', name='sf_accounts'),
)
