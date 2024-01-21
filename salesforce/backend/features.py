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

    supports_select_for_update_with_limit = False

    # support select combinators:
    supports_select_union = False
    supports_select_intersection = False
    supports_select_difference = False

    supports_aggregate_filter_clause = False

    # features for Django 3.0
    can_create_inline_fk = False

    if DJANGO_30_PLUS:
        can_return_columns_from_insert = True
        can_return_rows_from_bulk_insert = True
    else:
        can_return_id_from_insert = True
        can_return_ids_from_bulk_insert = True

    # TODO These options are the only from Django 2.2 that can be useful
    #      for something implemented here in future: Atomic, SFDX
    # autocommits_when_autocommit_is_off = True
    # ignores_table_name_case = True

    supported_explain_formats = set(['JSON'])

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

    supports_partial_indexes = False  # Django 2.2+
    supports_table_check_constraints = False

    can_introspect_json_field = False  # Django 3.1+
    supports_deferrable_unique_constraints = False
    supports_json_field = False

    supports_collation_on_charfield = False  # Django 3.2+
    supports_collation_on_textfield = False
    supports_non_deterministic_collations = False
    supports_covering_indexes = False
    supports_expression_indexes = False
    # django_test_expected_failures = set()  # maybe in the future
    # django_test_skips = {}

    supports_update_conflicts = False  # new in Django 4.1+
    supports_update_conflicts_with_target = False
    supports_logical_xor = False
    has_case_insensitive_like = True  # this is opposite to the default in Django 4.1+

    allows_group_by_select_index = False  # new in Django 4.2+
    schema_editor_uses_clientside_param_binding = False
    requires_compound_order_by_subquery = False
    # Does the backend support column and table comments?
    supports_comments = False
    # Does the backend support column comments in ADD COLUMN statements?
    supports_comments_inline = False
    # Does the backend support unlimited character columns?
    supports_unlimited_charfield = False

    # requires_literal_defaults = True  # TODO
