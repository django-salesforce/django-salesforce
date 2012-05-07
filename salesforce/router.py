from salesforce import models

class ModelRouter(object):
	"""
	Database router for Salesforce models.
	"""
	def db_for_read(self, model, **hints):
		return isinstance(model, models.SalesforceModel)

	def db_for_write(self, model, **hints):
		return isinstance(model, models.SalesforceModel)

	def allow_relation(self, obj1, obj2, **hints):
		return None

	def allow_syncdb(self, db, model):
		return db == 'default'
