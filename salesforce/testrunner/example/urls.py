# django-salesforce
#
# by Hyneck Cernoch and Phil Christensen
# See LICENSE.md for details
#

from django.urls import path
from . import views

urlpatterns = [
    path(r'', views.list_accounts, name='list_accounts'),
    path(r'search/', views.search_accounts, name='search_accounts'),
]
