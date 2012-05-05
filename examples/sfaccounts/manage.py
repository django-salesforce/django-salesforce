#!/usr/bin/env python

# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sfaccounts.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
