import re

from django.db.backends import BaseDatabaseOperations

class DatabaseOperations(BaseDatabaseOperations):
	compiler_module = "salesforce.backend.compiler"
	
	def __init__(self, connection):
		super(DatabaseOperations, self).__init__()
		self.connection = connection

	def quote_name(self, name):
		if name.startswith('"') and name.endswith('"'):
			return name # Quoting once is enough.
		return '"%s"' % name
