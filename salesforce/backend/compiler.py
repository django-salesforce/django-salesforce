# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Generate queries using the SOQL dialect.
"""
import re
from django.db import models
from django.db.models.sql import compiler, query, where, constants, AND, OR
from django.db.models.sql.datastructures import EmptyResultSet
from . import subselect

from salesforce import DJANGO_18_PLUS, DJANGO_19_PLUS
DJANGO_17_EXACT = not DJANGO_18_PLUS


class SQLCompiler(compiler.SQLCompiler):
    """
    A subclass of the default SQL compiler for the SOQL dialect.
    """
    soql_trans = None

    def resolve_columns(self, row, fields):
        # This method (conversion from row dict to list) is necessary only for
        # SF raw query, but if it exists then it is used by all SOQL queries.
        return [row[field.column] for field in fields]

    def get_columns(self, with_aliases=False):
        """
        Remove table names and strip quotes from column names.
        """
        soql_trans = self.query_topology()
        cols, col_params = compiler.SQLCompiler.get_columns(self, with_aliases)
        out = []
        for col in cols:
            if soql_trans and re.match(r'^\w+\.\w+$', col):
                tab_name, col_name = col.split('.')
                out.append('%s.%s' % (soql_trans[tab_name], col_name))
            else:
                out.append(col)
        cols = out
        result = [x.replace(' AS ', ' ') for x in cols]
        return (result, col_params)

    def get_from_clause(self):
        """
        Return the FROM clause, converted the SOQL dialect.

        It should be only the name of base object, even in parent-to-child and
        child-to-parent relationships queries.
        """
        self.query_topology()
        root_table = self.soql_trans[self.root_alias]
        return [root_table], []

    def quote_name_unless_alias(self, name):
        """
        A wrapper around connection.ops.quote_name that doesn't quote aliases
        for table names. Mostly used during the ORDER BY clause.
        """
        r = self.connection.ops.quote_name(name)
        self.quote_cache[name] = r
        return r

    def execute_sql(self, result_type=constants.MULTI):
        """
        Run the query against the database and returns the result(s). The
        return value is a single data item if result_type is SINGLE, or an
        iterator over the results if the result_type is MULTI.

        result_type is either MULTI (use fetchmany() to retrieve all rows),
        SINGLE (only retrieve a single row), or None. In this last case, the
        cursor is returned if any query is executed, since it's used by
        subclasses such as InsertQuery). It's possible, however, that no query
        is needed, as the filters describe an empty set. In that case, None is
        returned, to avoid any unnecessary database interaction.
        """
        try:
            sql, params = self.as_sql()
            if not sql:
                raise EmptyResultSet
        except EmptyResultSet:
            if result_type == constants.MULTI:
                return iter([])
            else:
                return

        cursor = self.connection.cursor(self.query)
        cursor.execute(sql, params)

        if not result_type or result_type == 'cursor':
            return cursor

        if DJANGO_18_PLUS:
            ordering_aliases = None
        else:
            ordering_aliases = self.ordering_aliases
        if result_type == constants.SINGLE:
            if ordering_aliases:
                return cursor.fetchone()[:-len(ordering_aliases)]
            return cursor.fetchone()

        # The MULTI case.
        if ordering_aliases:
            result = compiler.order_modified_iter(cursor, len(ordering_aliases),
                    self.connection.features.empty_fetchmany_value)
        else:
            result = iter((lambda: cursor.fetchmany(constants.GET_ITERATOR_CHUNK_SIZE)),
                    self.connection.features.empty_fetchmany_value)
        if not self.connection.features.can_use_chunked_reads:
            # If we are using non-chunked reads, we return the same data
            # structure as normally, but ensure it is all read into memory
            # before going any further.
            return list(result)
        return result

    if DJANGO_18_PLUS:  # or Django 1.9
        def as_sql(self, with_limits=True, with_col_aliases=False, subquery=False):
            """
            Creates the SQL for this query. Returns the SQL string and list of
            parameters.

            If 'with_limits' is False, any limit/offset information is not included
            in the query.
            """
            # After executing the query, we must get rid of any joins the query
            # setup created. So, take note of alias counts before the query ran.
            # However we do not want to get rid of stuff done in pre_sql_setup(),
            # as the pre_sql_setup will modify query state in a way that forbids
            # another run of it.
            if DJANGO_19_PLUS:
                if with_limits and self.query.low_mark == self.query.high_mark:
                    return '', ()
            self.subquery = subquery
            refcounts_before = self.query.alias_refcount.copy()
            soql_trans = self.query_topology()
            try:
                extra_select, order_by, group_by = self.pre_sql_setup()
                if with_limits and self.query.low_mark == self.query.high_mark:
                    return '', ()
                distinct_fields = self.get_distinct()

                # This must come after 'select', 'ordering', and 'distinct' -- see
                # docstring of get_from_clause() for details.
                from_, f_params = self.get_from_clause()

                if DJANGO_19_PLUS:
                    where, w_params = self.compile(self.where) if self.where is not None else ("", [])
                    having, h_params = self.compile(self.having) if self.having is not None else ("", [])
                else:
                    where, w_params = self.compile(self.query.where)
                    having, h_params = self.compile(self.query.having)
                params = []
                result = ['SELECT']

                if self.query.distinct:
                    result.append(self.connection.ops.distinct_sql(distinct_fields))

                out_cols = []
                col_idx = 1
                for _, (s_sql, s_params), alias in self.select + extra_select:
                    if alias:
                        # fixed by removing 'AS'
                        s_sql = '%s %s' % (s_sql, self.connection.ops.quote_name(alias))
                    elif with_col_aliases:
                        s_sql = '%s AS %s' % (s_sql, 'Col%d' % col_idx)
                        col_idx += 1
                    if soql_trans and re.match(r'^\w+\.\w+$', s_sql):
                        tab_name, col_name = s_sql.split('.')
                        s_sql = '%s.%s' % (soql_trans[tab_name], col_name)
                    params.extend(s_params)
                    out_cols.append(s_sql)

                result.append(', '.join(out_cols))

                result.append('FROM')
                result.extend(from_)
                params.extend(f_params)

                if where:
                    result.append('WHERE %s' % where)
                    params.extend(w_params)

                grouping = []
                for g_sql, g_params in group_by:
                    grouping.append(g_sql)
                    params.extend(g_params)
                if grouping:
                    if distinct_fields:
                        raise NotImplementedError(
                            "annotate() + distinct(fields) is not implemented.")
                    if not order_by:
                        order_by = self.connection.ops.force_no_ordering()
                    result.append('GROUP BY %s' % ', '.join(grouping))

                if having:
                    result.append('HAVING %s' % having)
                    params.extend(h_params)

                if order_by:
                    ordering = []
                    for _, (o_sql, o_params, _) in order_by:
                        ordering.append(o_sql)
                        params.extend(o_params)
                    result.append('ORDER BY %s' % ', '.join(ordering))

                if with_limits:
                    if self.query.high_mark is not None:
                        result.append('LIMIT %d' % (self.query.high_mark - self.query.low_mark))
                    if self.query.low_mark:
                        if self.query.high_mark is None:
                            val = self.connection.ops.no_limit_value()
                            if val:
                                result.append('LIMIT %d' % val)
                        result.append('OFFSET %d' % self.query.low_mark)

                if self.query.select_for_update and self.connection.features.has_select_for_update:
                    if self.connection.get_autocommit():
                        raise TransactionManagementError(
                            "select_for_update cannot be used outside of a transaction."
                        )

                    # If we've been asked for a NOWAIT query but the backend does
                    # not support it, raise a DatabaseError otherwise we could get
                    # an unexpected deadlock.
                    nowait = self.query.select_for_update_nowait
                    if nowait and not self.connection.features.has_select_for_update_nowait:
                        raise DatabaseError('NOWAIT is not supported on this database backend.')
                    result.append(self.connection.ops.for_update_sql(nowait=nowait))

                return ' '.join(result), tuple(params)
            finally:
                # Finally do cleanup - get rid of the joins we created above.
                self.query.reset_refcounts(refcounts_before)

    # nothing special needed for as_sql in Django 1.7

    def query_topology(self, _alias_map_items=None):
        # SOQL for SFDC requires:
        # - multiple (N-1) relations between (N) tables are possible
        # - exactly one top controlling table
        # - every relation is a join from exactly one foreign key to
        #   one primary key named "Id".
        #
        # Reorder relations to be from the left to the right
        if self.soql_trans is not None:
            return self.soql_trans
        if not _alias_map_items and not self.query.alias_map:
            assert DJANGO_18_PLUS, "empty alias_map is possible due to field expr in Django 1.8"
            return []
        # Unified interface:
        #   alias_map_items = [(lhs, table, join_cols_, rhs),...]
        query = self.query
        if _alias_map_items:
            alias_map_items = _alias_map_items
        elif DJANGO_18_PLUS:
            alias_map_items = [(getattr(v, 'parent_alias', None), v.table_name,
                               getattr(v, 'join_cols', None), v.table_alias
                              ) for v in query.alias_map.values()]
        else: # Django 1.7
            alias_map_items = [(v.lhs_alias, v.table_name, v.join_cols, v.rhs_alias)
                               for v in query.alias_map.values()]
        # Analyze
        alias2table = {}
        side_l, side_r = set(), set()
        for (lhs, table, join_cols_, rhs) in alias_map_items:
            alias2table[rhs] = table
            if lhs is not None:
                (join_cols,) = join_cols_
                assert len(join_cols) == 2
                # swap left-right if necessary. The left should be the top.
                if join_cols[0] == 'Id':
                    assert join_cols[1] != 'Id'
                    lhs, rhs = rhs, lhs
                    join_cols = join_cols[1], join_cols[0]
                assert join_cols[1] == 'Id'
                side_l.add(lhs)
                side_r.add(rhs)
            else:
                side_l.add(rhs)
        assert len(alias2table) == len(alias_map_items)
        # Recognize the top table
        assert len(side_l.union(side_r)) == len(alias_map_items)
        top_lhs_set = set(side_l).difference(side_r)
        assert len(top_lhs_set) == 1, ("Only queries with one top child model are "
                                       "supported by Salesforce. Use a subquery.")
        (top_lhs,) = top_lhs_set
        self.root_alias = top_lhs
        # translation rules into SOQL
        soql_trans = {top_lhs: alias2table[top_lhs]}
        work_lhses = set([top_lhs])
        while work_lhses:
            new_work = set()
            for (lhs, table, join_cols_, rhs) in alias_map_items:
                if lhs is not None:
                    (join_cols,) = join_cols_
                    if join_cols[0] == 'Id':
                        # swap lhs rhs
                        lhs, rhs = rhs, lhs
                        join_cols = join_cols[1], join_cols[0]
                    if lhs in work_lhses:
                        assert not rhs in soql_trans
                        if join_cols[0].endswith('__c'):
                            fkey = re.sub('__c$', '__r', join_cols[0])
                        else:
                            assert join_cols[0].endswith('Id')
                            fkey = re.sub('Id$', '', join_cols[0])
                        soql_trans[rhs] = '%s.%s' % (soql_trans[lhs], fkey)
                        new_work.add(rhs)
            work_lhses = new_work
        assert len(soql_trans) == len(alias_map_items)
        self.soql_trans = soql_trans
        return self.soql_trans

    def late_fix(self, sql):
        """Fix the WHERE condition in old Django 1.6"""
        assert not re.search(r'[\\"\']', sql)
        replacements = self.query_topology()
        # the replaced string is a alphanumeric word, including underscore
        assert all(re.match(r'^\w+$', x) for x in replacements.keys())
        pattern_replaced = re.compile(r'(?<=[^.\w])(%s)(?=\.\w+[^.\w])' % '|'.join(replacements.keys()))
        def func(sql):
            start = 0
            out = []
            for match in pattern_replaced.finditer(sql):
                out.append(sql[start:match.start()])
                out.append(replacements[match.group(1)])
                start = match.end()
            out.append(sql[start:len(sql)])
            return ''.join(out)
        return subselect.transform_except_subselect(sql, func)


class SalesforceWhereNode(where.WhereNode):
    overridden_types = ['isnull']

    def make_atom(self, child, qn, connection):
        # The make_atom() method is ignored in Django 1.7 unless explicitely required.
        # Use Lookup class instead. The make_atom() method will be removed in Django 1.9.
        lvalue, lookup_type, value_annot, params_or_value = child
        result = super(SalesforceWhereNode, self).make_atom(child, qn, connection)

        if(lookup_type in self.overridden_types):
            if hasattr(lvalue, 'process'):
                try:
                    lvalue, params = lvalue.process(lookup_type, params_or_value, connection)
                except where.EmptyShortCircuit:
                    raise EmptyResultSet
            if isinstance(lvalue, tuple):
                # A direct database column lookup.
                field_sql = self.sql_for_columns(lvalue, qn, connection)
            else:
                # A smart object with an as_sql() method.
                field_sql = lvalue.as_sql(qn, connection)

            if lookup_type == 'isnull':
                return ('%s %snull' % (field_sql,
                    (not value_annot and '!= ' or '= ')), ())
        else:
            return result


    # TODO compare, how much it is updated to 1.7
    # patched "django.db.models.sql.where.WhereNode.as_sql" from Django 1.5, 1.6., 1.7
    def as_sql(self, qn, connection):
        """
        Returns the SQL version of the where clause and the value to be
        substituted in. Returns '', [] if this node matches everything,
        None, [] if this node is empty, and raises EmptyResultSet if this
        node can't match anything.
        """
        # Note that the logic here is made slightly more complex than
        # necessary because there are two kind of empty nodes: Nodes
        # containing 0 children, and nodes that are known to match everything.
        # A match-everything node is different than empty node (which also
        # technically matches everything) for backwards compatibility reasons.
        # Refs #5261.

        soql_trans = qn.query_topology()
        result = []
        result_params = []
        everything_childs, nothing_childs = 0, 0
        non_empty_childs = len(self.children)

        for child in self.children:
            try:
                if hasattr(child, 'as_sql'):
                    # patch begin (combined Django 1.7)
                    sql, params = qn.compile(child)
                    # patch end
                else:
                    # A leaf node in the tree.
                    sql, params = self.make_atom(child, qn, connection)
            except EmptyResultSet:
                nothing_childs += 1
            else:
                if sql:
                    x_match = re.match(r'(\w+)\.(.*)', sql)
                    if x_match:
                        x_table, x_field = x_match.groups()
                        sql = '%s.%s' % (soql_trans[x_table], x_field)
                        #print('sql params:', sql, params)
                    result.append(sql)
                    result_params.extend(params)
                else:
                    if sql is None:
                        # Skip empty childs totally.
                        non_empty_childs -= 1
                        continue
                    everything_childs += 1
            # Check if this node matches nothing or everything.
            # First check the amount of full nodes and empty nodes
            # to make this node empty/full.
            if self.connector == AND:
                full_needed, empty_needed = non_empty_childs, 1
            else:
                full_needed, empty_needed = 1, non_empty_childs
            # Now, check if this node is full/empty using the
            # counts.
            if empty_needed - nothing_childs <= 0:
                if self.negated:
                    return '', []
                else:
                    raise EmptyResultSet
            if full_needed - everything_childs <= 0:
                if self.negated:
                    raise EmptyResultSet
                else:
                    return '', []

        if non_empty_childs == 0:
            # All the child nodes were empty, so this one is empty, too.
            return None, []
        conn = ' %s ' % self.connector
        sql_string = conn.join(result)
        if sql_string:
            if self.negated:
                # patch begin
                # SOQL requires parentheses around "NOT" if combined with AND/OR
                # sql_string = 'NOT (%s)' % sql_string
                sql_string = '(NOT (%s))' % sql_string
                # patch end
            elif len(result) > 1:
                sql_string = '(%s)' % sql_string
        return sql_string, result_params

    def add(self, data, conn_type, **kwargs):
        # The filter lookup `isnull` is very special and can not be
        # replaced only by `models.Field.register_lookup`. Otherwise the
        # register_lookup is preferred.
        cond = isinstance(data, models.lookups.IsNull) and not isinstance(data, IsNull)
        if cond:
            # "lhs" and "rhs" means Left and Right Hand Side of an condition
            data = IsNull(data.lhs, data.rhs)
        return super(SalesforceWhereNode, self).add(data, conn_type, **kwargs)

    as_salesforce = as_sql
    del as_sql

#   def as_salesforce(self, qn, connection):
#       import pprint
#       print('join_map:')
#       pprint.PrettyPrinter(width=80).pprint(qn.query.join_map)
#       import pdb; pdb.set_trace()
#       return self.as_sql(qn, connection)


class SQLInsertCompiler(compiler.SQLInsertCompiler, SQLCompiler):
    def execute_sql(self, return_id=False):
        assert not (return_id and len(self.query.objs) != 1)
        self.return_id = return_id
        cursor = self.connection.cursor(query=self.query)
        for sql, params in self.as_sql():
            cursor.execute(sql, params)
        if not return_id:
            return
        return self.connection.ops.last_insert_id(cursor,
                self.query.model._meta.db_table, self.query.model._meta.pk.column)


class SQLDeleteCompiler(compiler.SQLDeleteCompiler, SQLCompiler):
    pass

class SQLUpdateCompiler(compiler.SQLUpdateCompiler, SQLCompiler):
    pass

class SQLAggregateCompiler(compiler.SQLAggregateCompiler, SQLCompiler):
    pass

if DJANGO_17_EXACT:
    class SQLDateCompiler(compiler.SQLDateCompiler, SQLCompiler):
        pass


# Lookups
class IsNull(models.lookups.IsNull):
    # The expected result base class above is `models.lookups.IsNull`.
    lookup_name = 'isnull'

    def as_sql(self, qn, connection):
        if connection.vendor == 'salesforce':
            sql, params = qn.compile(self.lhs)
            return ('%s %s null' % (sql, ('=' if self.rhs else '!='))), params
        else:
            return super(IsNull, self).as_sql(qn, connection)

models.Field.register_lookup(IsNull)


class Range(models.lookups.Range):
    # The expected result base class above is `models.lookups.Range`.
    lookup_name = 'range'

    def as_sql(self, qn, connection):
        if connection.vendor == 'salesforce':
            lhs, lhs_params = self.process_lhs(qn, connection)
            rhs, rhs_params = self.process_rhs(qn, connection)
            if DJANGO_17_EXACT:
                rhs = [rhs, rhs]
            assert rhs == ['%s', '%s']
            params = lhs_params + rhs_params[:1] + lhs_params + rhs_params[1:2]
            # The symbolic parameters %s are again substituted by %s. The real
            # parameters will be passed finally directly to CursorWrapper.execute
            return '(%s >= %s AND %s <= %s)' % (lhs, rhs[0], lhs, rhs[1]), params
        else:
            return super(Range, self).as_sql(qn, connection)

models.Field.register_lookup(Range)

if DJANGO_18_PLUS:
    from django.db.models.aggregates import Count
    def count_as_salesforce(self, *args, **kwargs):
        if (len(self.source_expressions) == 1 and
                isinstance(self.source_expressions[0], models.expressions.Value) and
                self.source_expressions[0].value == '*'):
            return 'COUNT(Id)', []
        else:
            #tmp = Count('pk')
            #args[0].query.add_annotation(Count('pk'), alias='__count', is_summary=True)
            #obj.add_annotation(Count('*'), alias='__count', is_summary=True
            #self.source_expressions[0] = models.expressions.Col('__count', args[0].query.model._meta.fields[0])  #'Id'
            return self.as_sql(*args, **kwargs)
    setattr(Count, 'as_salesforce', count_as_salesforce)
