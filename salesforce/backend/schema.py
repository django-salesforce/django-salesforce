"""
Minimal code to support ignored makemigrations  (like django.db.backends.*.schema)

without interaction to SF (without migrate)
"""
from django.db import NotSupportedError
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

from salesforce.backend import log


class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):
    # pylint:disable=abstract-method  # undefined: prepare_default, quote_value

    def __init__(self, connection, collect_sql=False, atomic=True):
        self.connection_orig = connection
        self.collect_sql = collect_sql
        # if self.collect_sql:
        #    self.collected_sql = []
        super(DatabaseSchemaEditor, self).__init__(connection, collect_sql=collect_sql, atomic=atomic)

    # State-managing methods

    def __enter__(self):
        self.deferred_sql = []  # pylint:disable=attribute-defined-outside-init
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            for sql in self.deferred_sql:
                self.execute(sql)

    def execute(self, sql, params=()):
        if (sql == 'CREATE TABLE django_migrations ()'
                or sql.startswith('DROP TABLE ')) and not params:
            return
        raise NotSupportedError("Migration SchemaEditor: %r, %r" % (sql, params))

    def create_model(self, model):
        log.info("Skipped in SchemaEditor: create_model %s", model)
