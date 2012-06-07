# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

"""
Salesforce object manager.

Use a custom QuerySet to generate SOQL queries and results.
"""

from django.db.models import manager

from salesforce.backend import compiler

class SalesforceManager(manager.Manager):
	use_for_related_fields = True
	
	def get_query_set(self):
		"""
		Returns a QuerySet which access remote SF objects.
		"""
		from salesforce.backend import query
		q = query.SalesforceQuery(self.model, where=compiler.SalesforceWhereNode)
		return query.SalesforceQuerySet(self.model, query=q, using=self.db)

