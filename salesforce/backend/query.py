# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce object query and queryset customizations.  (like django.db.models.query)
"""
from typing import Dict, Generic, Iterable, List, Optional, TYPE_CHECKING, Type, TypeVar
import typing
import warnings

from django.conf import settings
from django.db import NotSupportedError, models
from django.db.models import query as models_query, Model
from django.db.utils import DEFAULT_DB_ALIAS
import django

from salesforce.backend.indep import get_sf_alt_pk
from salesforce.backend import compiler, DJANGO_20_PLUS, DJANGO_22_PLUS, DJANGO_30_PLUS
from salesforce.backend.models_sql_query import SalesforceQuery
from salesforce.router import is_sf_database
import salesforce.backend.utils

_T = TypeVar("_T", bound=models.Model, covariant=True)
if TYPE_CHECKING:
    from salesforce.models import SalesforceModel  # noqa

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

    def __init__(self,
                 model: Optional[Type[_T]] = None,
                 query: Optional['SalesforceQuery[_T]'] = None,
                 using: Optional[str] = None,
                 hints: Optional[Dict[str, Model]] = None
                 ) -> None:
        if query is None:
            query = SalesforceQuery(model, where=compiler.SalesforceWhereNode)
        super().__init__(model=model, query=query, using=using, hints=hints)

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
        return self.sf(query_all=True)

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

    def sf(self,
           query_all: Optional[bool] = None,
           all_or_none: Optional[bool] = None,
           edge_updates: Optional[bool] = None,
           ) -> 'SalesforceQuerySet[_T]':
        """Set additional parameters for queryset methods with Salesforce.

        see details about these parameters in `salesforce.backend.models_sql_query.SalesforceQuery.sf(...)`

        It is better to put this method near the beginning of the chain of queryset methods.

        Example:
        >>> Contact.objects.sf(all_or_none=True).bulk_create([Contact(last_name='a')])
        """
        if not is_sf_database(self.db):
            return self
        clone = self._chain()
        clone.query = clone.query.sf(
            query_all=query_all,
            all_or_none=all_or_none,
            edge_updates=edge_updates,
        )
        return clone

    def _chain(self, **kwargs) -> 'SalesforceQuerySet[_T]':
        if DJANGO_20_PLUS:
            return super()._chain(**kwargs)
        else:
            return self._clone(**kwargs)  # type: ignore[call-arg] # noqa

    def patch_insert_query(self, query: models.sql.Query) -> None:
        setattr(query, 'sf_params', self.query.sf_params)

    # original Django method '._insert(...)' patched by .patch_insert_query(...)
    if DJANGO_30_PLUS:
        def _insert(self, objs, fields, returning_fields=None, raw=False, using=None, ignore_conflicts=False):
            self._for_write = True
            if using is None:
                using = self.db
            query = models.sql.InsertQuery(self.model, ignore_conflicts=ignore_conflicts)
            self.patch_insert_query(query)  # patch
            query.insert_values(fields, objs, raw=raw)
            return query.get_compiler(using=using).execute_sql(returning_fields)
    elif DJANGO_22_PLUS:
        def _insert(self, objs, fields, return_id=False, raw=False, using=None, ignore_conflicts=False):  # type: ignore[misc] # noqa
            """
            Insert a new record for the given model. This provides an interface to
            the InsertQuery class and is how Model.save() is implemented.
            """
            self._for_write = True
            if using is None:
                using = self.db
            query = models.sql.InsertQuery(self.model, ignore_conflicts=ignore_conflicts)
            self.patch_insert_query(query)  # patch
            query.insert_values(fields, objs, raw=raw)
            return query.get_compiler(using=using).execute_sql(return_id)
    else:
        def _insert(self, objs, fields, return_id=False, raw=False, using=None):  # type: ignore[misc] # noqa
            self._for_write = True
            if using is None:
                using = self.db
            query = models.sql.InsertQuery(self.model)
            self.patch_insert_query(query)  # patch
            query.insert_values(fields, objs, raw=raw)
            return query.get_compiler(using=using).execute_sql(return_id)
    _insert.alters_data = True  # type: ignore[attr-defined]  # noqa
    _insert.queryset_only = False  # type: ignore[attr-defined]  # noqa


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
