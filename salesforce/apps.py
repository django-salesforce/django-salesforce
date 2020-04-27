"""This file is useful only if 'salesforce' is a duplicit name in Django registry

then put a string 'salesforce.apps.SalesforceDb' instead of simple 'salesforce'
"""
from django.apps import AppConfig


class SalesforceDb(AppConfig):
    name = 'salesforce'
    label = 'salesforce_db'
