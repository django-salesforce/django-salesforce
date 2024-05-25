"""
Lookups  (like django.db.models.lookups, django.db.models.aggregates.Count)

Every overridden class here must be registered either:
- registered by '@Field.register_lookup' if the parent class is registered
or must be
- setattr(parent_class, 'as_salesforce', overridden_class)  if the parent class is not registered
"""
from django.db import models
from django.db.models.fields import Field
from django.db.models import lookups


class IsNull(models.lookups.IsNull):  # pylint:disable=abstract-method
    def override_as_sql(self, compiler, connection):  # pylint:disable=unused-argument
        # it will be relabeled later by sf_fix_field() to prevent a problematic double relabel
        lhs, params = self.process_lhs(compiler, connection)
        operator = '=' if self.rhs else '!='
        return f"{lhs} {operator} null", params

    setattr(models.lookups.IsNull, 'as_salesforce', override_as_sql)


class Range(models.lookups.Range):  # pylint:disable=abstract-method
    def override_as_sql(self, compiler, connection):
        lhs, lhs_params = self.process_lhs(compiler, connection)
        rhs, rhs_params = self.process_rhs(compiler, connection)
        assert rhs == ('%s', '%s')
        assert len(rhs_params) == 2
        params = lhs_params + [rhs_params[0]] + lhs_params + [rhs_params[1]]
        lhs = compiler.sf_fix_field(lhs)
        return f'({lhs} >= %s AND {lhs} <= %s)', params

    setattr(models.lookups.Range, 'as_salesforce', override_as_sql)


class Count(models.aggregates.Count):
    # pylint:disable=abstract-method,too-many-ancestors  # undefined __and__, __or__, __rand__, __ror__

    def override_as_sql(self, *args, **kwargs):
        if len(self.source_expressions) == 1 and isinstance(self.source_expressions[0], models.expressions.Star):
            # patch for compile "Count('*')
            # (an alternative verbose solution is: f"COUNT({args[0].query.model._meta.db_table}.Id)")
            return 'COUNT(Id)', []
        # compile a normal Count('some_field')
        sql, params = self.as_sql(*args, **kwargs)
        if sql.startswith('COUNT(DISTINCT '):
            sql = sql.replace('COUNT(DISTINCT ', 'COUNT_DISTINCT(')
        return sql, params

    setattr(models.aggregates.Count, 'as_salesforce', override_as_sql)


@Field.register_lookup
class NotIn(lookups.In):  # pylint:disable=abstract-method
    lookup_name = 'not_in'

    def get_rhs_op(self, connection, rhs):
        return 'NOT IN %s' % rhs

    def split_parameter_list_as_sql(self, compiler, connection):
        # this patch is a only for Oracle and never tested with it
        max_size = connection.ops.max_in_list_size()
        raise NotImplementedError("Lookup 'not_in' can't be used with lists longer then %d" % max_size)


@Field.register_lookup
class NotEqual(lookups.Exact):  # pylint:disable=abstract-method
    lookup_name = 'not_eq'

    def get_rhs_op(self, connection, rhs):
        return '!= %s' % rhs


class YearLookup(lookups.YearLookup):
    def override_as_sql(self, compiler, connection):
        sql, params = self.as_sql(compiler, connection)
        lhs, *rest = sql.split(' ', 1)
        if rest == ["BETWEEN %s AND %s"]:
            lhs = compiler.sf_fix_field(lhs)
            sql = f"({lhs} >= %s AND {lhs} <= %s)"
        return sql, params

    setattr(lookups.YearLookup, 'as_salesforce', override_as_sql)
