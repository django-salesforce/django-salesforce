from django.db.models import manager

class SalesforceManager(manager.Manager):
	def get_query_set(self):
		"""
		Returns a QuerySet which access remote resources.
		"""
		from salesforce.backend import query
		return query.SalesforceQuerySet(self.model)

