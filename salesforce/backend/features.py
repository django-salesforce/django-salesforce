"""
Database features  (like django.db.backends.*.features)
"""
from django.db.backends.base.features import BaseDatabaseFeatures


class DatabaseFeatures(BaseDatabaseFeatures):
    """
    Features this database provides.
    """
    allows_group_by_pk = True
    supports_unspecified_pk = False
    can_return_id_from_insert = True
    can_return_ids_from_bulk_insert = True
    has_bulk_insert = True
    # TODO If the following would be True, it requires a good relation name resolution
    supports_select_related = False
    # Though Salesforce doesn't support transactions, the setting
    # `supports_transactions` is used only for switching between rollback or
    # cleaning the database in testrunner after every test and loading fixtures
    # before it, however SF does not support any of these and all test data must
    # be loaded and cleaned by the testcase code. From the viewpoint of SF it is
    # irrelevant, but due to issue #28 (slow unit tests) it should be True.
    supports_transactions = True

    # Never use `interprets_empty_strings_as_nulls=True`. It is an opposite
    # setting for Oracle, while Salesforce saves nulls as empty strings not vice
    # versa.
