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

__version__ = "0.7.2"

DJANGO_18_PLUS = True  # unused by us now - backward compatibility
DJANGO_19_PLUS = django.VERSION[:2] >= (1, 9)
DJANGO_110_PLUS = django.VERSION[:2] >= (1, 10)
DJANGO_111_PLUS = django.VERSION[:2] >= (1, 11)
DJANGO_20_PLUS = django.VERSION[:2] >= (2, 0)
if django.VERSION[:2] < (1, 10):
    # Statistically three or more blocking issues can be expected by every
    # new major Django version. Strict check before support is better.
    raise ImportError("Django version of at least 1.10 is required "
                      "for this django-salesforce.")

log = logging.getLogger(__name__)

# Default version of Force.com API.
# It can be set by setattr() to any lower or higher supported value.
# (The highest version can be set by "salesforce.utils.set_highest_api_version()".
# It is useful for development, a constant version is for production.)

# Example for settings.py:
# >>> import salesforce
# >>> setattr(salesforce, 'API_VERSION', '37.0')

API_VERSION = '44.0'  # Winter '19
