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

def is_sf_database(db, model=None):
	"""The alias is a Salesforce database."""
	from django.db import connections
	from salesforce.backend.base import DatabaseWrapper
	if db is None:
		return getattr(model, '_salesforce_object', False)
	else:
		engine = connections[db].settings_dict['ENGINE']
		return (engine == 'salesforce.backend' or
				isinstance(connections[db], DatabaseWrapper))


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

	def allow_migrate(self, db, model):
		"""
		Don't attempt to sync SF models to non SF databases and vice versa.
		"""
		if hasattr(model, '_salesforce_object'):
			# If SALESFORCE_DB_ALIAS is e.g. a sqlite3 database, than it can migrate SF models
			if not (is_sf_database(db) or db == self.sf_alias):
				return False
		else:
			if is_sf_database(db):
				return False
		# TODO: It is usual that syncdb is currently disallowed for SF but in
		# the future it can be allowed to do deep check of compatibily Django
		# models with SF models by introspection.
		if(hasattr(model, '_salesforce_object')):
			#return False
			pass
		# Nothing is said about non SF models with non SF databases, because
		# it can be solved by other routers, otherwise is enabled if all
		# routers say None.
	
	# alias for Django 1.6 and older. The new name is useful for query_all etc.
	allow_syncdb = allow_migrate
