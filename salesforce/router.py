# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

"""
Database router for SalesforceModel objects.
"""

from django.conf import settings

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
		if isinstance(model, models.SalesforceModel):
			return self.sf_alias
		if issubclass(model, models.SalesforceModel):
			return self.sf_alias

	def db_for_write(self, model, **hints):
		"""
		If passed a class or instance, return the salesforce alias if it's a subclass of SalesforceModel.
		"""
		from salesforce import models
		if isinstance(model, models.SalesforceModel):
			return self.sf_alias
		if issubclass(model, models.SalesforceModel):
			return self.sf_alias

	def allow_relation(self, obj1, obj2, **hints):
		"""
		Salesforce doesn't support relations in the traditional sense.
		"""
		return None

	def allow_syncdb(self, db, model):
		"""
		Don't attempt to sync the salesforce database connection.
		"""
		return db != self.sf_alias
