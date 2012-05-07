from django.core.exceptions import ImproperlyConfigured
from django.db.backends import BaseDatabaseIntrospection

def complain(*args, **kwargs):
	raise ImproperlyConfigured("DatabaseIntrospection: Not yet implemented for the Salesforce backend.")

class DatabaseIntrospection(BaseDatabaseIntrospection):
	get_table_list = complain
	get_table_description = complain
	get_relations = complain
	get_indexes = complain

