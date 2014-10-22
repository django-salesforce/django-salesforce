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
from django.db.utils import DEFAULT_DB_ALIAS

from salesforce import router, DJANGO_16_PLUS
from salesforce.backend import sf_alias

class SalesforceManager(manager.Manager):
	use_for_related_fields = True
	
	def get_queryset(self):
		"""
		Returns a QuerySet which access remote SF objects.
		"""
		if not router.is_sf_database(self.db):
			if DJANGO_16_PLUS:
				return super(SalesforceManager, self).get_queryset()
			else:
				return super(SalesforceManager, self).get_query_set()
		else:
			from salesforce.backend import query, compiler
			q = query.SalesforceQuery(self.model, where=compiler.SalesforceWhereNode)
			return query.SalesforceQuerySet(self.model, query=q, using=self.db)

	#if not DJANGO_16_PLUS:  - keep back obsoleted qs is better than to get broken qs.
	get_query_set = get_queryset

	def using(self, alias):
		if alias is None:
			if getattr(self.model, '_salesforce_object', False):
				alias = sf_alias
			else:
				alias = DEFAULT_DB_ALIAS
		if router.is_sf_database(alias, self.model):
			return self.get_queryset().using(alias)
		else:
			return super(SalesforceManager, self).using(alias)

	def raw(self, raw_query, params=None, *args, **kwargs):
		if router.is_sf_database(self.db):
			from salesforce.backend import query
			q = query.SalesforceRawQuery(raw_query, self.db, params)
			return query.SalesforceRawQuerySet(raw_query=raw_query, model=self.model, query=q, params=params, using=self.db)
		else:
			return super(SalesforceManager, self).raw(raw_query, params, *args, **kwargs)

	def query_all(self):
		if router.is_sf_database(self.db):
			return self.get_queryset().query_all()
		else:
			return self.get_queryset()
