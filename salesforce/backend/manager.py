from django.db.models import manager

from salesforce.backend import compiler

class SalesforceManager(manager.Manager):
	def get_query_set(self):
		"""
		Returns a QuerySet which access remote resources.
		"""
		from salesforce.backend import query
		q = query.SalesforceQuery(self.model, where=compiler.SalesforceWhereNode)
		return query.SalesforceQuerySet(self.model, query=q, using=self.db)

