"""
Customized Query, RawQuery  (like django.db.models.sql.query)
"""
from django.conf import settings
from django.db.models import Count
from django.db.models.sql import Query, RawQuery, constants

from salesforce.backend import DJANGO_20_PLUS
from salesforce.dbapi.driver import arg_to_soql


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


class SalesforceQuery(Query):
    """
    Override aggregates.
    """
    def __init__(self, *args, **kwargs):
        super(SalesforceQuery, self).__init__(*args, **kwargs)
        self.is_query_all = False
        self.max_depth = 1

    def __str__(self):
        """Return the query as merged SOQL for Salesforce"""
        sql, params = self.sql_with_params()
        return sql % tuple(arg_to_soql(x) for x in params)

    def sql_with_params(self):
        """
        Return the query as an SOQL string and the parameters for Salesforce.

        It is a shortcut for debugging, unused by backends.
        (It ignores "using(...)". because the exact alias is known only in
        queryset, but not in a query.)
        """
        sf_alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
        return self.get_compiler(sf_alias).as_sql()

    def clone(self, klass=None, memo=None):  # pylint: disable=arguments-differ
        if DJANGO_20_PLUS:
            query = Query.clone(self)
        else:
            query = Query.clone(self, klass, memo)  # pylint: disable=too-many-function-args
        query.is_query_all = self.is_query_all
        return query

    def has_results(self, using):
        q = self.clone()
        compiler = q.get_compiler(using=using)  # pylint: disable=no-member
        return bool(compiler.execute_sql(constants.SINGLE))

    def set_query_all(self):
        self.is_query_all = True

    def get_count(self, using):
        # TODO maybe can be removed soon
        """
        Performs a COUNT() query using the current filter constraints.
        """
        obj = self.clone()
        obj.add_annotation(Count('pk'), alias='x_sf_count', is_summary=True)  # pylint: disable=no-member
        number = obj.get_aggregation(using, ['x_sf_count'])['x_sf_count']  # pylint: disable=no-member
        if number is None:
            number = 0
        return number
