# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce object query and queryset customizations.  (like django.db.models.query)
"""
from typing import Generic, Iterable, List, Optional, TYPE_CHECKING, TypeVar
import typing
import warnings

from django.conf import settings
from django.db import NotSupportedError, models
from django.db.models import query as models_query
from django.db.utils import DEFAULT_DB_ALIAS
import django

from salesforce.backend.indep import get_sf_alt_pk
from salesforce.backend import DJANGO_20_PLUS, DJANGO_22_PLUS
from salesforce.backend.models_sql_query import SalesforceQuery
from salesforce.router import is_sf_database
import salesforce.backend.utils

_T = TypeVar("_T", bound=models.Model, covariant=True)

# class SalesforceRawQuerySet(query.RawQuerySet):
#     def __len__(self):
#         if self.query.cursor is None:
#             # force the query
#             self.query.get_columns()
#         return self.query.cursor.rowcount


class SalesforceQuerySet(models_query.QuerySet, Generic[_T]):
    """
    Use a custom SQL compiler to generate SOQL-compliant queries.
    """
    if TYPE_CHECKING:
        query = None  # type: SalesforceQuery[_T]

    def using(self, alias: Optional[str]) -> 'SalesforceQuerySet[_T]':
        if alias is None:
            if hasattr(self.model, '_salesforce_object'):
                alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
            else:
                alias = DEFAULT_DB_ALIAS
        return super().using(alias)

    def query_all(self) -> 'SalesforceQuerySet[_T]':
        """
        Allows querying for also deleted or merged records.
            Lead.objects.query_all().filter(IsDeleted=True,...)
        https://www.salesforce.com/us/developer/docs/api_rest/Content/resources_queryall.htm

        It is ignored on non-salesforce databases.
        """
        if not is_sf_database(self.db):
            return self
        clone = self._chain()
        clone.query.set_query_all()
        return clone

    def simple_select_related(self, *fields: str) -> 'SalesforceQuerySet[_T]':
        if DJANGO_20_PLUS:
            raise NotSupportedError("Obsoleted method .simple_select_related(), use .select_related() instead")
        warnings.warn("Obsoleted method .simple_select_related(), use .select_related() instead")
        return self.select_related(*fields)

    def bulk_create(self, objs: Iterable[_T], batch_size: Optional[int] = None, ignore_conflicts: bool = False
                    ) -> List[_T]:
        # parameter 'ignore_conflicts=False' is new in Django 2.2
        kwargs = {'ignore_conflicts': ignore_conflicts} if DJANGO_22_PLUS else {}
        if getattr(self.model, '_salesforce_object', '') == 'extended' and not is_sf_database(self.db):
            objs = list(objs)
            for x in objs:
                if x.pk is None:
                    x.pk = get_sf_alt_pk()
        return super(SalesforceQuerySet, self).bulk_create(objs, batch_size=batch_size, **kwargs)

    def sf(self, **kwargs) -> 'SalesforceQuerySet[_T]':
        """Set Salesforce parameters for a queryset methods

        Example:
        >>> Contact.objects.sf(all_or_none=True).bulk_create([Contact(last_name='a')])
        """
        if not is_sf_database(self.db):
            return self
        clone = self._chain()
        return clone

    if not DJANGO_20_PLUS:
        def _chain(self, **kwargs) -> 'SalesforceQuerySet[_T]':
            return self._clone()


def bulk_update_small(objs: 'typing.Collection[models.Model]', fields: Iterable[str], all_or_none: bool = None
                      ) -> None:
    # simple implementation without "batch_size" parameter, but with "all_or_none"
    # and objects from mixed models can be updated by one request in the same transaction
    assert len(objs) <= 200
    records = []
    dbs = set()
    for item in objs:
        query = django.db.models.sql.subqueries.UpdateQuery(item._meta.model)  # fake query
        query.add_update_values({field: getattr(item, field) for field in fields})
        values = salesforce.backend.utils.extract_values(query)
        values['id'] = item.pk
        values['type_'] = item._meta.db_table
        records.append(values)
        dbs.add(item._state.db)
    db = dbs.pop()
    if dbs or not is_sf_database(db):
        raise ValueError("All updated objects must be from the same Salesforce database.")
    connection = django.db.connections[db].connection
    connection.sobject_collections_request('PATCH', records, all_or_none=all_or_none)
