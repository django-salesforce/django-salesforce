# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#
"""
Salesforce Database backend for Django.

No code in this directory is used with standard databases, even if a standard
database is used for running some application tests on objects defined by
SalesforceModel. All code for SF models that can be used with non SF databases
should be located directly in the 'salesforce' directory in files 'models.py',
'fields.py', 'router.py', 'admin.py', 'backend/manager.py'.

Most of code here (in salesforce.backend) is private. (undocumented like other
Django backends and can be changed anytime. Therefore it should not be used by apps)
The only public code here is `salesforce/backend/manager.py`.

Structure:
    salesforce/*.py - Code that is to be used instead of some standard
                      django.db classes.
    salesforce/backend/*.py - Private code equivalent to django.db.backend.some_backend
    salesforce/dbapi/*.py - Database driver independent on Django

Incorrectly located files: (It is better not to change it now.)
    backend/manager.py   => manager.py
    auth.py              => dbapi/auth.py
"""

import logging
import re

import django

DJANGO_20_PLUS = django.VERSION[:2] >= (2, 0)
DJANGO_21_PLUS = django.VERSION[:2] >= (2, 1)
DJANGO_22_PLUS = django.VERSION[:2] >= (2, 2)
DJANGO_30_PLUS = django.VERSION[:2] >= (3, 0)
DJANGO_31_PLUS = django.VERSION[:2] >= (3, 1)  # still only a development version exists
is_dev_version = django.VERSION[3:] and re.match('(alpha|beta|rc)', django.VERSION[3])
if django.VERSION[:2] < (1, 11) or django.VERSION[:2] > (3, 1) and not is_dev_version:
    raise ImportError("Django version between 1.11 and 3.1 is required "
                      "for this django-salesforce.")
    # Usually three or more blocking issues can be expected by every
    # new major Django version. Strict check before support is better.

    # New Django development versions are enabled without any restriction, but
    # new stable Django versions must be verified before they can be enabled here.


log = logging.getLogger(__name__)
