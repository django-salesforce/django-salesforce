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

def is_testing(db):
	from django.db import connections
	from salesforce.backend.base import DatabaseWrapper 
	return not isinstance(connections[db], DatabaseWrapper)

class ModelRouter(object):
	"""
	Database router for Salesforce models.
	"""
	sf_alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
	
	def db_for_read(self, model, **hints):
		"""
		If passed a class or instance, return the salesforce alias if it's a subclass of SalesforceModel.
		"""
		from salesforce import models
		if getattr(model, '_salesforce_object', False):
			return self.sf_alias

	def db_for_write(self, model, **hints):
		"""
		If passed a class or instance, return the salesforce alias if it's a subclass of SalesforceModel.
		"""
		from salesforce import models
		if getattr(model, '_salesforce_object', False):
			return self.sf_alias

	def allow_syncdb(self, db, model):
		"""
		Don't attempt to sync salesforce models.
		"""
		if(is_testing(db)):
			return True
		if(db == self.sf_alias):
			return False
		if(hasattr(model, '_salesforce_object')):
			return False
