#!/usr/bin/env python

# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

import os
from django.core.management import execute_manager

# note that we're actually running the testrunner project, not the salesforce app.
os.environ['DJANGO_SETTINGS_MODULE'] = 'salesforce.testrunner.settings'

if __name__ == "__main__":
	from salesforce.testrunner import settings
	execute_manager(settings)
