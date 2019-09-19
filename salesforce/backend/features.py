"""
Database features  (like django.db.backends.*.features)
"""
from django.db.backends.base.features import BaseDatabaseFeatures
from salesforce.backend import DJANGO_30_PLUS


class DatabaseFeatures(BaseDatabaseFeatures):
    """
    Features this database provides.
    """
    allows_group_by_pk = True
    supports_unspecified_pk = False
    has_bulk_insert = True
    uses_savepoints = False

    can_introspect_duration_field = False
    supports_partial_indexes = False
    supports_ignore_conflicts = True

    supports_select_for_update_with_limit = False  # since Django 1.7

    # features new in Django 1.11
    supports_select_union = False
    supports_select_intersection = False
    supports_select_difference = False

    # features for Django 3.0
    can_create_inline_fk = False

    if DJANGO_30_PLUS:
        can_return_columns_from_insert = True
        can_return_rows_from_bulk_insert = True  # pylint:disable=invalid-name
    else:
        can_return_id_from_insert = True
        can_return_ids_from_bulk_insert = True

    # TODO These options are the only from Django 2.2 that can be useful
    #      for something implemented here in future: Atomic, SFDX, Explain
    # autocommits_when_autocommit_is_off = True
    # ignores_table_name_case = True
    # supported_explain_formats = set()

    # Though Salesforce doesn't support transactions, the setting
    # `supports_transactions` is used only for switching between rollback or
    # cleaning the database in testrunner after every test and loading fixtures
    # before it, however SF does not support any of these. All test data must
    # be loaded and cleaned by the testcase code. From the viewpoint of SF it is
    # irrelevant, but due to issue #28 (slow unit tests) it should be True.
    supports_transactions = True

    # Never use `interprets_empty_strings_as_nulls=True`. It is an opposite
    # setting for Oracle, while Salesforce saves nulls as empty strings not vice
    # versa.
