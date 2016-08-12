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

__version__ = "0.6.9"

DJANGO_18_PLUS = django.VERSION[:2] >= (1, 8)
DJANGO_19_PLUS = django.VERSION[:3] >= (1, 9)
DJANGO_110_PLUS = django.VERSION[:3] >= (1, 10)
if django.VERSION[:2] < (1, 7) or (1, 8, 0) <= django.VERSION[:3] < (1, 8, 4):
    raise ImportError("Django 1.7 or higher is required for django-salesforce "
                      "and versions between 1.8 and 1.8.3 are unsupported.")

log = logging.getLogger(__name__)

# Default version of Force.com API.
# It can be set by setattr() to any lower or higher supported value.
# (The highest version can be set by "salesforce.utils.set_highest_api_version()".
# It is useful for development, a constant version is for production.)

# Example for settings.py:
# >>> import salesforce
# >>> setattr(salesforce, 'API_VERSION', '37.0')

API_VERSION = '37.0'  # Summer '16
