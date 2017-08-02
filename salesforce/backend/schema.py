"""
Minimal code to support makemigrations also in Django 1.10+

without interaction to SF (without migrate)
"""
# from django.db.backends.base.schema import BaseDatabaseSchemaEditor


# class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):
class DatabaseSchemaEditor(object):

    def __init__(self, connection, collect_sql=False):
        self.connection_orig = connection
        self.collect_sql = collect_sql
        # if self.collect_sql:
        #    self.collected_sql = []

    # State-managing methods

    def __enter__(self):
        self.deferred_sql = []
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            for sql in self.deferred_sql:
                self.execute(sql)

    def execute(self, sql, params=[]):
        if sql == 'CREATE TABLE django_migrations ()' and params is None:
            return
        raise NotImplementedError("Migration SchemaEditor: %r, %r" % (sql, params))

    def create_model(self, model):
        print("Skipped in SchemaEditor: create_model %s" % model)
