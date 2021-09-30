# django-salesforce
#
# by Hyneck Cernoch and Phil Christensen
# See LICENSE.md for details
#

"""
Salesforce object query and queryset customizations.  (like django.db.models.query)
"""
from typing import Dict, Generic, Iterable, List, NoReturn, Optional, TYPE_CHECKING, Type, TypeVar
import typing  # pylint:disable=unused-import

from django.conf import settings
from django.db import NotSupportedError, models, DEFAULT_DB_ALIAS
from django.db.models import constants
from django.db.models import query as models_query, Model
from django.db.models.sql import where as sql_where
import django

from salesforce.backend.indep import get_sf_alt_pk
from salesforce.backend import compiler, DJANGO_22_PLUS, DJANGO_30_PLUS, DJANGO_40_PLUS, DJANGO_41_PLUS
from salesforce.backend.models_sql_query import SalesforceQuery
from salesforce.backend.operations import BULK_BATCH_SIZE
from salesforce.router import is_sf_database
import salesforce.backend.utils

_T = TypeVar("_T", bound=models.Model, covariant=True)
if TYPE_CHECKING:
    from salesforce.models import SalesforceModel  # pylint:disable=cyclic-import # noqa
    # pylint:enable=cyclic-import

# class SalesforceRawQuerySet(query.RawQuerySet):
#     def __len__(self):
#         if self.query.cursor is None:
#             # force the query
#             self.query.get_columns()
#         return self.query.cursor.rowcount

if DJANGO_40_PLUS and not hasattr(sql_where.WhereNode, 'as_salesforce'):
    setattr(sql_where.WhereNode, 'as_salesforce', compiler.SalesforceWhereNode.as_salesforce)


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
            if DJANGO_40_PLUS:
                query = SalesforceQuery(model)
            else:
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

    def simple_select_related(self, *fields: str) -> NoReturn:  # pylint:disable=no-self-use
        raise NotSupportedError("Obsoleted method .simple_select_related(), use .select_related() instead")

    def bulk_create(self, objs: Iterable[_T], batch_size: Optional[int] = None,
                    ignore_conflicts: bool = False,
                    update_conflicts: bool = False,
                    update_fields: Optional[List[str]] = None,
                    unique_fields: Optional[List[str]] = None,
                    ) -> List[_T]:
        # parameter 'ignore_conflicts=False' is new in Django 2.2
        kwargs = {'ignore_conflicts': ignore_conflicts} if DJANGO_22_PLUS else {}
        assert not update_conflicts and update_fields is None and unique_fields is None
        if getattr(self.model, '_salesforce_object', '') == 'extended' and not is_sf_database(self.db):
            objs = list(objs)
            for x in objs:
                if x.pk is None:
                    x.pk = get_sf_alt_pk()
        return super().bulk_create(objs, batch_size=batch_size, **kwargs)

    def bulk_update(self, objs: Iterable[Model], fields: 'typing.Collection[str]',  # pylint:disable=arguments-differ
                    batch_size: Optional[int] = None, all_or_none: bool = None):
        self.sf(all_or_none=all_or_none)
        if batch_size is not None and batch_size < 0:
            raise ValueError('Batch size must be a positive integer.')
        batch_size = min(batch_size, BULK_BATCH_SIZE) if batch_size else BULK_BATCH_SIZE
        for chunk in salesforce.backend.utils.chunked(objs, batch_size):
            bulk_update_small(chunk, fields, all_or_none=all_or_none)

    def sf(self,
           query_all: Optional[bool] = None,
           all_or_none: Optional[bool] = None,
           edge_updates: Optional[bool] = None,
           minimal_aliases: Optional[bool] = None,
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
            minimal_aliases=minimal_aliases,
        )
        return clone

    # def _chain(self, **kwargs) -> 'SalesforceQuerySet[_T]':
    #     return super()._chain(**kwargs)

    def patch_insert_query(self, query: models.sql.Query) -> None:
        setattr(query, 'sf_params', self.query.sf_params)

    # original Django method '._insert(...)' patched by .patch_insert_query(...)
    if DJANGO_41_PLUS:
        def _insert(self, objs, fields,
                    returning_fields=None, raw=False, using=None, on_conflict=None,
                    update_fields=None, unique_fields=None):
            assert on_conflict is None or on_conflict == constants.OnConflict.IGNORE  # pylint:disable=no-member
            assert update_fields is None and unique_fields is None
            self._for_write = True
            if using is None:
                using = self.db
            query = models.sql.InsertQuery(self.model, on_conflict=on_conflict)
            self.patch_insert_query(query)  # patch
            query.insert_values(fields, objs, raw=raw)
            return query.get_compiler(using=using).execute_sql(returning_fields)
    elif DJANGO_30_PLUS:
        def _insert(self, objs, fields,  # type: ignore[misc] # pylint:disable=arguments-differ
                    returning_fields=None, raw=False, using=None, ignore_conflicts=False):
            self._for_write = True
            if using is None:
                using = self.db
            query = models.sql.InsertQuery(self.model, ignore_conflicts=ignore_conflicts)
            self.patch_insert_query(query)  # patch
            query.insert_values(fields, objs, raw=raw)
            return query.get_compiler(using=using).execute_sql(returning_fields)
    elif DJANGO_22_PLUS:
        def _insert(self, objs, fields,  # type: ignore[misc] # pylint:disable=arguments-differ
                    return_id=False, raw=False, using=None, ignore_conflicts=False):
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
        def _insert(self, objs, fields, return_id=False,  # type: ignore[misc] # pylint:disable=arguments-differ
                    raw=False, using=None):
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
    assert len(objs) <= BULK_BATCH_SIZE
    records = []
    dbs = set()
    for item in objs:
        query = django.db.models.sql.subqueries.UpdateQuery(item._meta.model)  # fake query
        query.add_update_values({field: getattr(item, field) for field in fields})
        values = salesforce.backend.utils.extract_update_values(query)
        values['id'] = item.pk
        values['type_'] = item._meta.db_table
        records.append(values)
        dbs.add(item._state.db)  # pylint:disable=protected-access
    db = dbs.pop()
    if dbs or not is_sf_database(db):
        raise ValueError("All updated objects must be from the same Salesforce database.")
    connection = django.db.connections[db].connection
    connection.sobject_collections_request('PATCH', records, all_or_none=all_or_none)
