# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

"""
Automatic table creation is not supported at this time.
"""

from django.db.backends.creation import BaseDatabaseCreation

class DatabaseCreation(BaseDatabaseCreation):
	pass
