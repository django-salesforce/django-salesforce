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

__version__ = "0.6.9"  # development shortly before 0.7

DJANGO_18_PLUS = True  # unused by us now - backward compatibility
DJANGO_19_PLUS = django.VERSION[:2] >= (1, 9)
DJANGO_110_PLUS = django.VERSION[:2] >= (1, 10)
DJANGO_111_PLUS = django.VERSION[:2] >= (1, 11)
if django.VERSION[:3] < (1, 8, 4) or django.VERSION[:2] > (1, 11):
    # Statistically three or more blocking issues can be expected by every
    # new major Django version. Strict check before support is better.
    raise ImportError("Django version between 1.8.4 and 1.11.x is required "
                      "for this django-salesforce.")

if DJANGO_111_PLUS:
    warnings.warn("Support for Django 1.11 is still in pre-release quality. "
                  "Test your app properly after upgraging.")

log = logging.getLogger(__name__)

# Default version of Force.com API.
# It can be set by setattr() to any lower or higher supported value.
# (The highest version can be set by "salesforce.utils.set_highest_api_version()".
# It is useful for development, a constant version is for production.)

# Example for settings.py:
# >>> import salesforce
# >>> setattr(salesforce, 'API_VERSION', '37.0')

API_VERSION = '39.0'  # Spring '17
