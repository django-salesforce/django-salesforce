"""
creating the custom urls for access the LPS Patient Connect Portal

@author Preston Mackert
"""

from django.urls import path
from . import views

urlpatterns = [
    path(r'', views.index, name='index'),
    path(r'sp_portal/', views.list_specialty_pharmacy_status, name='sp_portal'),
    path(r'search_sp_updates/', views.search_sp_updates, name='search_sp_updates')
]
