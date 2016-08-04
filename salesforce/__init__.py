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

__version__ = "0.6.3"

DJANGO_18_PLUS = django.VERSION[:2] >= (1, 8)
DJANGO_19_PLUS = django.VERSION[:3] >= (1, 9)
DJANGO_110_PLUS = django.VERSION[:3] >= (1, 10)
if django.VERSION[:2] < (1, 7) or (1, 8, 0) <= django.VERSION[:3] < (1, 8, 4):
    raise ImportError("Django 1.7 or higher is required for django-salesforce "
                      "and versions between 1.8 and 1.8.3 are unsupported.")

log = logging.getLogger(__name__)
