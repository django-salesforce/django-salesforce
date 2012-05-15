from django.db.models import manager
from django.db.models.sql import Query

from salesforce.backend import compiler

class SalesforceManager(manager.Manager):
	def get_query_set(self):
		"""
		Returns a QuerySet which access remote resources.
		"""
		from salesforce.backend import query
		q = Query(self.model, where=compiler.SalesforceWhereNode)
		return query.SalesforceQuerySet(self.model, query=q, using=self.db)

