# django-salesforce
#
# by Hyneck Cernoch and Phil Christensen
# See LICENSE.md for details
#

"""
Salesforce object manager. (like django.db.models.manager)

Use a custom QuerySet to generate SOQL queries and results.

This module requires a customized package django-stubs (django-salesforce-stubs)
"""

from typing import Generic, Optional, TypeVar
from django.db.models import manager, Model
from django.db.models.query import QuerySet  # pylint:disable=unused-import

from salesforce import router
from salesforce.backend import query

_T = TypeVar("_T", bound=Model, covariant=True)


class SalesforceManager(manager.Manager, Generic[_T]):

    def get_queryset(self, _alias: Optional[str] = None) -> 'QuerySet[_T]':
        """
        Returns a QuerySet which access remote SF objects.
        """
        alias_is_sf = _alias and router.is_sf_database(_alias)
        is_extended_model = getattr(self.model, '_salesforce_object', '') == 'extended'
        assert self.model is not None
        if router.is_sf_database(self.db) or alias_is_sf or is_extended_model:
            return query.SalesforceQuerySet(self.model, using=self.db)
        return super().get_queryset()

    # def raw(self, raw_query, params=None, translations=None):
    #     if router.is_sf_database(self.db):
    #         q = models_sql_query.SalesforceRawQuery(raw_query, self.db, params)
    #         return query.SalesforceRawQuerySet(raw_query=raw_query, model=self.model, query=q,
    #                                            params=params, using=self.db)
    #     return super().raw(raw_query, params=params, translations=translations)

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
           minimal_aliases: Optional[bool] = None) -> 'query.SalesforceQuerySet[_T]':
        # not dry, but explicit due to preferring type check of user code
        qs = self.get_queryset()
        assert isinstance(qs, query.SalesforceQuerySet)
        return qs.sf(
            query_all=query_all,
            all_or_none=all_or_none,
            edge_updates=edge_updates,
            minimal_aliases=minimal_aliases,
        )
