# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.list_accounts, name='list_accounts'),
    url(r'^search/$', views.search_accounts, name='search_accounts'),
]
