# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce object manager. (like django.db.models.manager)

Use a custom QuerySet to generate SOQL queries and results.

This module is important for run-time, ignored in type checking and
correct results are made by by sustomized django-stubs (django-salesforce-stubs)
"""

import sys
from typing import Generic, Optional, TypeVar
from django.db.models import manager, Model
from django.db.models.query import QuerySet

from salesforce import router
from salesforce.backend import query, DJANGO_20_PLUS

_T = TypeVar("_T", bound=Model, covariant=True)


class SalesforceManager(manager.Manager, Generic[_T]):

    if sys.version_info[:2] < (3, 6):
        # this is a fix for Generic type issue https://github.com/python/typing/issues/498
        __copy__ = None

    if not DJANGO_20_PLUS:
        use_for_related_fields = True
        silence_use_for_related_fields_deprecation = True  # pylint:disable=invalid-name  # name from Django

    def get_queryset(self, _alias: Optional[str] = None) -> 'QuerySet[_T]':
        """
        Returns a QuerySet which access remote SF objects.
        """
        alias_is_sf = _alias and router.is_sf_database(_alias)
        is_extended_model = getattr(self.model, '_salesforce_object', '') == 'extended'
        assert self.model is not None
        if router.is_sf_database(self.db) or alias_is_sf or is_extended_model:
            return query.SalesforceQuerySet(self.model, using=self.db)
        return super(SalesforceManager, self).get_queryset()

    # def raw(self, raw_query, params=None, translations=None):
    #     if router.is_sf_database(self.db):
    #         q = models_sql_query.SalesforceRawQuery(raw_query, self.db, params)
    #         return query.SalesforceRawQuerySet(raw_query=raw_query, model=self.model, query=q,
    #                                            params=params, using=self.db)
    #     return super(SalesforceManager, self).raw(raw_query, params=params, translations=translations)

    # methods of SalesforceQuerySet on a SalesfroceManager

    def query_all(self) -> 'query.SalesforceQuerySet[_T]':  # type: ignore[override] # noqa
        qs = self.get_queryset()
        assert isinstance(qs, query.SalesforceQuerySet)
        ret = qs.query_all()
        return ret

    def sf(self,
           query_all: Optional[bool] = None,
           all_or_none: Optional[bool] = None,
           edge_updates: Optional[bool] = None,
           ) -> 'query.SalesforceQuerySet[_T]':
        # not dry, but explicit due to preferring type check of user code
        qs = self.get_queryset()
        assert isinstance(qs, query.SalesforceQuerySet)
        return qs.sf(
            query_all=query_all,
            all_or_none=all_or_none,
            edge_updates=edge_updates,
        )
