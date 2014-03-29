# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Automatic table creation is not supported by the Salesforce backend.
"""

from django.db.backends.creation import BaseDatabaseCreation

class DatabaseCreation(BaseDatabaseCreation):
	def create_test_db(self, verbosity=1, autoclobber=False):
		test_database_name = self._get_test_db_name()
		
		if verbosity >= 1:
			test_db_repr = ''
			if verbosity >= 2:
				test_db_repr = " ('%s')" % test_database_name
			print("Ignoring test database creation for alias '%s'%s..." % (self.connection.alias, test_db_repr))
		
		return test_database_name
	
	def destroy_test_db(self, old_database_name, verbosity=1):
		test_database_name = self.connection.settings_dict['NAME']
		if verbosity >= 1:
			test_db_repr = ''
			if verbosity >= 2:
				test_db_repr = " ('%s')" % test_database_name
			print("No test database to destroy for alias '%s'%s..." % (self.connection.alias, test_db_repr))
		self.connection.settings_dict['NAME'] = old_database_name

