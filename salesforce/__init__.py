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
import warnings

import django
DJANGO_18_PLUS = django.VERSION[:2] >= (1, 8)
DJANGO_184_PLUS = django.VERSION[:3] >= (1, 8, 4)
if not django.VERSION[:2] >= (1, 7):
	raise ImportError("Django 1.7 or higher is required for django-salesforce.")
if django.VERSION[:2] >= (1, 8):
	warnings.warn("The support for Django 1.8 is currently INCOMPLETE in django-salesforce. "
				  "Read the details in README and test your app carefully with Django 1.8")

log = logging.getLogger(__name__)
