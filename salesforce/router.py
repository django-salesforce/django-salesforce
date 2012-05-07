from salesforce import models

class ModelRouter(object):
	"""
	Database router for Salesforce models.
	"""
	def db_for_read(self, model, **hints):
		if isinstance(model, models.SalesforceModel):
			return 'salesforce'

	def db_for_write(self, model, **hints):
		if isinstance(model, models.SalesforceModel):
			return 'salesforce'

	def allow_relation(self, obj1, obj2, **hints):
		return None

	def allow_syncdb(self, db, model):
		return db == 'default'
