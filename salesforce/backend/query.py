# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce object query and queryset customizations.  (like django.db.models.query)
"""
from typing import Iterable, List, Optional, Type, TypeVar, cast
import typing
import warnings

from django.db import NotSupportedError, models
from django.db.models import query
import django

from salesforce.backend.indep import get_sf_alt_pk
from salesforce.backend import DJANGO_20_PLUS, DJANGO_22_PLUS
from salesforce.backend.models_sql_query import SalesforceQuery
from salesforce.router import is_sf_database
import salesforce.backend.utils

_T = TypeVar("_T", bound=models.Model, covariant=True)
_QS = TypeVar("_QS", bound="SalesforceQuerySet")

# class SalesforceRawQuerySet(query.RawQuerySet):
#     def __len__(self):
#         if self.query.cursor is None:
#             # force the query
#             self.query.get_columns()
#         return self.query.cursor.rowcount


class SalesforceQuerySet(query.QuerySet):
    """
    Use a custom SQL compiler to generate SOQL-compliant queries.
    """

    def query_all(self: _QS) -> _QS:
        """
        Allows querying for also deleted or merged records.
            Lead.objects.query_all().filter(IsDeleted=True,...)
        https://www.salesforce.com/us/developer/docs/api_rest/Content/resources_queryall.htm
        """
        if DJANGO_20_PLUS:
            obj = self._clone()  # type: _QS
        else:
            obj = self._clone(klass=cast(Type[_QS], SalesforceQuerySet))  # pylint: disable=unexpected-keyword-arg
        obj_query = obj.query
        assert isinstance(obj_query, SalesforceQuery), "Can't select deleted objects on a non-SF database"
        obj_query.set_query_all()
        return obj

    def simple_select_related(self: _QS, *fields: str) -> _QS:
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
