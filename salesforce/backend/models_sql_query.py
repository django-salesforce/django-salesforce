"""
Customized Query, RawQuery  (like django.db.models.sql.query)
"""
import copy
from typing import Any, cast, Generic, Optional, Sequence, Tuple, Type, TypeVar
from django.conf import settings
from django.db.models import Count, Model
from django.db.models.sql import Query, RawQuery, constants

from salesforce.backend import DJANGO_20_PLUS
from salesforce.dbapi.driver import arg_to_soql

_T = TypeVar("_T", bound=Model, covariant=True)


class SalesforceRawQuery(RawQuery):
    pass

#     def clone(self, using):
#         return SalesforceRawQuery(self.sql, using, params=self.params)
#
#     def get_columns(self):
#         if self.cursor is None:
#             self._execute_query()
#         converter = connections[self.using].introspection.table_name_converter
#         if self.cursor.rowcount > 0:
#             return [converter(col) for col in self.cursor.first_row.keys() if col != 'attributes']
#         # TODO hy: A more general fix is desirable with rewriting more code.
#         return ['Id']  # originally [SF_PK] before Django 1.8.4
#
#     def _execute_query(self):
#         self.cursor = connections[self.using].cursor()
#         self.cursor.prepare_query(self)
#         self.cursor.execute(self.sql, self.params)
#
#     def __repr__(self):
#         return "<SalesforceRawQuery: %s; %r>" % (self.sql, tuple(self.params))
#
#     def __iter__(self):
#         for row in super(SalesforceRawQuery, self).__iter__():
#             yield [row[k] for k in self.get_columns()]


class SfParams:  # like an immutable DataClass: clone when updating
    def __init__(self):
        self.query_all = False
        self.all_or_none = None  # type: Optional[bool]
        self.edge_updates = False


class SalesforceQuery(Query, Generic[_T]):
    """
    Override aggregates.
    """
    def __init__(self, model: Optional[Type[_T]], *args, **kwargs) -> None:
        super(SalesforceQuery, self).__init__(model, *args, **kwargs)
        self.max_depth = 1
        self.sf_params = SfParams()  # paramaters for Salesforce query instead of transaction control

    def __str__(self) -> str:
        """Return the query as merged SOQL for Salesforce"""
        sql, params = self.sql_with_params()
        return sql % tuple(arg_to_soql(x) for x in params)

    def sql_with_params(self) -> Tuple[str, Sequence[Any]]:
        """
        Return the query as an SOQL string and the parameters for Salesforce.

        It is a shortcut for debugging, unused by backends.
        (It ignores "using(...)". because the exact alias is known only in
        queryset, but not in a query.)
        """
        sf_alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
        return self.get_compiler(sf_alias).as_sql()

    def clone(self, klass=None, memo=None) -> 'SalesforceQuery[_T]':  # pylint: disable=arguments-differ
        if DJANGO_20_PLUS:
            query = cast(SalesforceQuery, Query.clone(self))
        else:
            # pylint: disable=too-many-function-args
            query = cast(SalesforceQuery, Query.clone(self, klass, memo))  # type: ignore[call-arg]  # noqa
            query.sf_params = self.sf_params
        return query

    def sf(self,
           query_all: Optional[bool] = None,
           all_or_none: Optional[bool] = None,
           edge_updates: Optional[bool] = None,
           ) -> 'SalesforceQuery[_T]':
        """
        Set additional parameters for a queryset

            `query_all`: True: Also deleted objects from the trash bin can be selected by this.
                These can be selected exclusively after that by `.filter(is_deleted=True)`

            `all_or_none`: This affects `bulk_create` and `bulk_update` methods. These methods
                         work by blocks of 200 items and it is a biggest possible transacion.
                True: All records in blocks are updated or no record is updated in a block with
                    the first error and no following block is tried. (small rolback and stop)
                False: All possible records in all blocks are updated.
                Default: No following block after an error is tried, but also no rollback is done
                    in a block with some errors. (This neutral behavior can not be set back after
                    True or False.)

            `edge_updates`: methods update() and delete() on querysets with related tables
                could be unsafe if the queryset is not checked. It safe to rewrite it to two
                nested querysets or if it is correct then if can be allowed by `edge_updates`.
                default is False.
        """
        clone = self.clone()
        clone.sf_params = copy.copy(self.sf_params)
        if query_all is not None:
            clone.sf_params.query_all = query_all
        if all_or_none is not None:
            clone.sf_params.all_or_none = all_or_none
        if edge_updates is not None:
            clone.sf_params.edge_updates = edge_updates
        return clone

    def has_results(self, using: Optional[str]) -> bool:
        q = self.clone()
        compiler = q.get_compiler(using=using)  # pylint: disable=no-member
        return bool(compiler.execute_sql(constants.SINGLE))

    def get_count(self, using: str) -> int:
        # TODO maybe can be removed soon
        """
        Performs a COUNT() query using the current filter constraints.
        """
        # customized because "Count('*')" is not possbel wit Salesforce and also not "__" in an alias
        obj = self.clone()
        obj.add_annotation(Count('pk'), alias='x_sf_count', is_summary=True)  # pylint: disable=no-member
        number = obj.get_aggregation(using, ['x_sf_count'])['x_sf_count']  # type: Optional[int] # pylint: disable=no-member # noqa
        if number is None:
            number = 0
        return number
