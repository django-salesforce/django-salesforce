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

import django.db.backends.utils
from django.utils.deconstruct import deconstructible
from django.db.backends.base.operations import BaseDatabaseOperations
from salesforce.backend import DJANGO_30_PLUS

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

        def fetch_returned_insert_columns(self, cursor):
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

    def return_insert_id(self):
        return "", ()


@deconstructible
class DefaultedOnCreate(object):
    """
    The default value which denotes that the value should skipped and
    replaced later on the SFDC server.

    It should not be replaced by Django, because SF can do it better or
    even no real ralue neither None is accepted.
    SFDC can set the correct value only if the field is omitted as the REST API.
    (No normal soulution exists e.g. for some builtin foreign keys with
    SF attributes 'defaultedOnCreate: true, nillable: false')

    Example: `Owner` field is assigned to the current user if the field User is omitted.

        Owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                default=models.DefaultedOnCreate(),
                db_column='OwnerId')
    """
    # pylint:disable=too-few-public-methods
    def __init__(self, arg=None):
        self.arg = arg

    def __str__(self):
        if self.arg is None:
            return 'DEFAULTED_ON_CREATE'
        return 'DefaultedOnCreate({})'.format(repr(self.arg))
