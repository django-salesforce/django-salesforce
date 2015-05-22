# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
A database backend for the Django ORM.

Allows access to all Salesforce objects accessible via the SOQL API.
"""
import logging
import ssl
import warnings

import django
DJANGO_15_PLUS = django.VERSION[:2] >= (1, 5)
DJANGO_16_PLUS = django.VERSION[:2] >= (1, 6)
DJANGO_17_PLUS = django.VERSION[:2] >= (1, 7)
DJANGO_18_PLUS = django.VERSION[:2] >= (1, 8)
if not django.VERSION[:2] >= (1, 4):
	raise ImportError("Django 1.4 or higher is required for django-salesforce.")
if django.VERSION[:2] >= (1, 8):
	warnings.warn("The support for Django 1.8 is currently INCOMPLETE in django-salesforce. "
				"Use Django 1.7 or read the details in README and test your app "
				"carefully with Django 1.8")

log = logging.getLogger(__name__)
