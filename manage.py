#!/usr/bin/env python

from django.core.management import execute_manager

import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'salesforce.testrunner.settings'

from salesforce.testrunner import settings

if __name__ == "__main__":
	execute_manager(settings)
