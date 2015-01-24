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

import django
DJANGO_15_PLUS = django.VERSION[:2] >= (1, 5)
DJANGO_16_PLUS = django.VERSION[:2] >= (1, 6)
DJANGO_17_PLUS = django.VERSION[:2] >= (1, 7)
if not django.VERSION[:2] >= (1, 4):
	raise ImportError("Django 1.4 or higher is required for django-salesforce.")

log = logging.getLogger(__name__)
