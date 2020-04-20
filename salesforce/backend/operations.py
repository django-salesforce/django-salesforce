# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#
"""
DatabaseOperations  (like salesforce.db.backends.*.operations)
"""
import itertools
import warnings

import django.db.backends.utils
from django.db.backends.base.operations import BaseDatabaseOperations
from salesforce.backend import DJANGO_30_PLUS
from salesforce.defaults import DefaultedOnCreate
from salesforce.dbapi.exceptions import SalesforceWarning

BULK_BATCH_SIZE = 200

"""
Default database operations, with unquoted names.
"""


class DatabaseOperations(BaseDatabaseOperations):
    # undefined abstract methods:
    #       date_extract_sql, date_interval_sql,     date_trunc_sql,  datetime_cast_date_sql
    #   datetime_extract_sql,                    datetime_trunc_sql,
    #                                                time_trunc_sql,  datetime_cast_time_sql;
    #   no_limit_value,   regex_lookup
    #
    # pylint:disable=abstract-method,no-self-use,unused-argument

    compiler_module = "salesforce.backend.compiler"

    def connection_init(self):
        pass

    def sql_flush(self, style, tables, sequences, allow_cascade=False):
        return []

    def quote_name(self, name):
        return name

    def value_to_db_datetime(self, value):
        """
        We let the JSON serializer handle dates for us.
        """
        return value

    def value_to_db_date(self, value):
        """
        We let the JSON serializer handle dates for us.
        """
        return value

    def last_insert_id(self, cursor, table_name, pk_name):
        return cursor.lastrowid

    if DJANGO_30_PLUS:

        def fetch_returned_insert_columns(self, cursor, returning_params=None):
            # the parameter "returning_params" is for Django 3.1
            return [cursor.lastrowid]

        def fetch_returned_insert_rows(self, cursor):
            return [[x] for x in cursor.lastrowid]

        def return_insert_columns(self, fields):
            return '', ()  # dummy result

    else:

        def fetch_returned_insert_id(self, cursor):
            return cursor.lastrowid

        def fetch_returned_insert_ids(self, cursor):
            return cursor.lastrowid

        def return_insert_id(self):
            return "", ()

    # A method max_in_list_size(self) would be not a solution, because it is
    # restricted by a maximal size of SOQL.
    # Splitting to more (... IN ...) OR (... IN ...) does not help.

    def adapt_datefield_value(self, value):
        return value

    def adapt_datetimefield_value(self, value):
        return value

    def adapt_timefield_value(self, value):
        return value

    def adapt_decimalfield_value(self, value, max_digits=None, decimal_places=None):
        if isinstance(value, DefaultedOnCreate):
            return value
        return django.db.backends.utils.format_number(value, max_digits, decimal_places)

    def bulk_batch_size(self, fields, objs):
        return BULK_BATCH_SIZE

    # This SQL is not important because we control the db from the compiler
    # but something must exist
    def bulk_insert_sql(self, fields, placeholder_rows):
        return "VALUES " + ", ".join(itertools.chain(*placeholder_rows))

    def conditional_expression_supported_in_where_clause(self, expression):
        """
        All filter elements in a WHERE clause must be a field compared with value.
        The same is necessary for boolean fields, e.g. IsActive=true
        """
        False

    def prep_for_like_query(self, x):
        """Prepare a value for use in a LIKE query."""
        if '\\' in x:
            warnings.warn("Backslash not allowed in LIKE expressions for Salesforce", SalesforceWarning)
        # A wildcard search is better than a search of '\\%' or '\\_', see #254
        return str(x)
        # return str(x).replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
