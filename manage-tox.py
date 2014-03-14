#!/usr/bin/env python

# This is a modified `manage.py` for running tests for Python 3 with `tox`.
# Even though the command `python3 setup.py install` installs the modified
# code prepared by `2to3`, the unmodified code incorrect for Python 3 is
# still in the current directory. Therefore must be the current directory
# on `sys.path` replaced by `./build/lib`.

import os
import sys

#if os.path.abspath('.') in os.path:
build_lib = 'build{0}/lib'.format('3' if sys.version_info[0] == 3 else '')
sys.path[sys.path.index(os.path.realpath('.'))] = os.path.realpath(build_lib)
os.chdir(os.path.abspath(build_lib))

# note that we're actually running the testrunner project, not the salesforce app.
os.environ['DJANGO_SETTINGS_MODULE'] = 'salesforce.testrunner.settings'

if __name__ == "__main__":
	from django.core.management import execute_from_command_line
	execute_from_command_line(sys.argv)
