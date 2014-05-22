# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce object manager.

Use a custom QuerySet to generate SOQL queries and results.
"""

import warnings
from django.db import connections
from django.db.models import manager
from django.db.models.query import RawQuerySet

from salesforce import router, DJANGO_17_PLUS

class SalesforceManager(manager.Manager):
	use_for_related_fields = True
	
	def get_query_set(self):
		"""
		Returns a QuerySet which access remote SF objects.
		"""
		if not router.is_sf_database(self.db):
			warnings.warn("Incorrectly called SalesforceManager. (probably)", DeprecationWarning)
			return super(SalesforceManager, self).get_query_set()
		else:
			from salesforce.backend import query, compiler
			q = query.SalesforceQuery(self.model, where=compiler.SalesforceWhereNode)
			return query.SalesforceQuerySet(self.model, query=q, using=self.db)

	if DJANGO_17_PLUS:
		get_queryset = get_query_set


	def raw(self, raw_query, params=None, *args, **kwargs):
		from salesforce.backend import query
		q = query.SalesforceRawQuery(raw_query, self.db, params)
		return query.SalesforceRawQuerySet(raw_query=raw_query, model=self.model, query=q, params=params, using=self.db)

	def query_all(self):
		return self.get_query_set().query_all()
