from django.core.exceptions import ImproperlyConfigured
from django.db.backends import BaseDatabaseClient

def complain(*args, **kwargs):
	raise ImproperlyConfigured("DatabaseClient: Not yet implemented for the Salesforce backend.")

class DatabaseClient(BaseDatabaseClient):
	runshell = complain
