# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Database router for SalesforceModel objects.
"""

import logging

from django.conf import settings

log = logging.getLogger(__name__)

def is_sf_database(db):
	"""The alias is a Salesforce database."""
	from django.db import connections
	from salesforce.backend.base import DatabaseWrapper 
	return isinstance(connections[db], DatabaseWrapper)

#def is_testing(db):
#	return not is_sf_database(db)

class ModelRouter(object):
	"""
	Database router for Salesforce models.
	"""
	sf_alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
	
	def db_for_read(self, model, **hints):
		"""
		If given some hints['instance'] that is saved in a db, use related
		fields from the same db. Otherwise if passed a class or instance to
		model, return the salesforce alias if it's a subclass of SalesforceModel.
		"""
		if 'instance' in hints:
			db = hints['instance']._state.db
			if db:
				return db
		if getattr(model, '_salesforce_object', False):
			return self.sf_alias

	def db_for_write(self, model, **hints):
		"""
		If given some hints['instance'] that is saved in a db, use related
		fields from the same db. Otherwise if passed a class or instance to
		model, return the salesforce alias if it's a subclass of SalesforceModel.
		"""
		if 'instance' in hints:
			db = hints['instance']._state.db
			if db:
				return db
		if getattr(model, '_salesforce_object', False):
			return self.sf_alias

	def allow_syncdb(self, db, model):
		"""
		Don't attempt to sync salesforce models or db.
		"""
		from django.db import connections
		if(is_testing(db)):
			return True
		if(connections[db].settings_dict['ENGINE'] == 'salesforce.backend'):
			return False
		if(hasattr(model, '_salesforce_object')):
			return False
