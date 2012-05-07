from django_roa.db import managers

class SalesforceManager(managers.ROAManager):
	def get_query_set(self):
		"""
		Returns a QuerySet which access remote resources.
		"""
		from salesforce.backend import query
		return query.SalesforceQuerySet(self.model)

