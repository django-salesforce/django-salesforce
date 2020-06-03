"""
Lookups  (like django.db.models.lookups, django.db.models.aggregates.Count)
"""
from django.db import models
from django.db.models.fields import Field
from django.db.models import lookups


class IsNull(models.lookups.IsNull):
    def override_as_sql(self, compiler, connection):  # pylint:disable=unused-argument
        # it must be relabeled if used for a children rows set
        sql, params = compiler.compile(self.lhs.relabeled_clone(compiler.soql_trans))
        return ('%s %s null' % (sql, ('=' if self.rhs else '!='))), params

    setattr(models.lookups.IsNull, 'as_salesforce', override_as_sql)


class Range(models.lookups.Range):
    def override_as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        assert tuple(rhs) == ('%s', '%s')  # tuple in Django 1.11+, list in old Django
        assert len(rhs_params) == 2
        params = lhs_params + [rhs_params[0]] + lhs_params + [rhs_params[1]]
        # The symbolic parameters %s are again substituted by %s. The real
        # parameters will be passed finally directly to CursorWrapper.execute
        return '(%s >= %s AND %s <= %s)' % (lhs, rhs[0], lhs, rhs[1]), params

    setattr(models.lookups.Range, 'as_salesforce', override_as_sql)


class Count(models.aggregates.Count):
    # pylint:disable=abstract-method,too-many-ancestors  # undefined __and__, __or__, __rand__, __ror__

    def override_as_sql(self, *args, **kwargs):
        if (len(self.source_expressions) == 1 and
                isinstance(self.source_expressions[0], models.expressions.Value) and
                self.source_expressions[0].value == '*'):
            return 'COUNT(Id)', []
        # a normal Count('some_field')
        # TODO write test for Count(... distinct=True)
        #     tests can use some of following:
        #     args[0].query.add_annotation(Count('pk'), alias='__count', is_summary=True)
        #     obj.add_annotation(Count('*'), alias='__count', is_summary=True
        #     self.source_expressions[0] = models.expressions.Col('__count', args[0].query.model._meta.fields[0])'
        sql, params = self.as_sql(*args, **kwargs)
        if sql.startswith('COUNT(DISTINCT '):
            sql = sql.replace('COUNT(DISTINCT ', 'COUNT_DISTINCT(')
        return sql, params

    setattr(models.aggregates.Count, 'as_salesforce', override_as_sql)


@Field.register_lookup
class NotIn(lookups.In):
    lookup_name = 'not_in'

    def get_rhs_op(self, connection, rhs):
        return 'NOT IN %s' % rhs

    def split_parameter_list_as_sql(self, compiler, connection):
        # this patch is a only for Oracle and never tested with it
        max_size = connection.ops.max_in_list_size()
        raise NotImplementedError("Lookup 'not_in' can't be used with lists longer then %d" % max_size)


@Field.register_lookup
class NotEqual(lookups.Exact):
    lookup_name = 'not_eq'

    def get_rhs_op(self, connection, rhs):
        return '!= %s' % rhs
