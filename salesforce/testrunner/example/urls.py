# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

from django.urls import path
from . import views

urlpatterns = [
    path(r'', views.list_accounts, name='list_accounts'),
    path(r'search/', views.search_accounts, name='search_accounts'),
]
