# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Generate queries using the SOQL dialect.  (like django.db.models.sql.compiler and  django.db.models.sql.where)
"""
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, TYPE_CHECKING
import re
from django.core.exceptions import EmptyResultSet
from django.db import NotSupportedError
from django.db.models.sql import compiler as sql_compiler, where as sql_where, constants, datastructures
from django.db.models.sql.where import AND
from django.db.transaction import TransactionManagementError

import salesforce.backend.models_lookups   # required for activation of lookups
from salesforce.backend import DJANGO_20_PLUS, DJANGO_21_PLUS, DJANGO_30_PLUS, DJANGO_31_PLUS
from salesforce.dbapi.driver import DatabaseError
if TYPE_CHECKING:
    import salesforce.backend.base
# pylint:no-else-return,too-many-branches,too-many-locals

AliasMapItems = List[Tuple[
    Optional[str],
    str,
    Optional[Tuple[Tuple[str, str], ...]],
    str
]]


class SQLCompiler(sql_compiler.SQLCompiler):
    """
    A subclass of the default SQL compiler for the SOQL dialect.
    """
    soql_trans = None  # type: Optional[Dict[str, str]]

    def __init__(self, *args, **kwargs) -> None:
        super(SQLCompiler, self).__init__(*args, **kwargs)
        self.root_aliases = []  # type: List[str]

    def get_from_clause(self) -> Tuple[List[str], List[Any]]:
        """
        Return the FROM clause, converted the SOQL dialect.

        It should be only the name of base object, even in parent-to-child and
        child-to-parent relationships queries.
        """
        self.query_topology()
        assert self.soql_trans
        if self.root_aliases and len(self.root_aliases) == 1:
            root_table = self.soql_trans[self.root_aliases[0]]
        else:
            sql_items, params = super(SQLCompiler, self).get_from_clause()
            assert not params
            root_table, alias = sql_items[0].rsplit(' ', 1)
            msg = "Only queries with one top child model are supported by Salesforce. Use a subquery."
            assert len(sql_items) == 1 and self.soql_trans.get(alias) == root_table, msg
        return [root_table], []

    def quote_name_unless_alias(self, name: str) -> str:
        """
        A wrapper around connection.ops.quote_name that doesn't quote aliases
        for table names. Mostly used during the ORDER BY clause.
        """
        r = self.connection.ops.quote_name(name)
        self.quote_cache[name] = r
        return r

    # patched and simplified the parend method  # pylint:disable=no-else-return
    def execute_sql(self,
                    result_type: str = constants.MULTI,
                    chunked_fetch: bool = False,
                    chunk_size: int = constants.GET_ITERATOR_CHUNK_SIZE
                    ) -> Any:
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

        cursor = self.connection.cursor()
        cursor.prepare_query(self.query)
        cursor.execute(sql, params)

        if not result_type or result_type == 'cursor':
            return cursor

        if result_type == constants.SINGLE:
            return cursor.fetchone()

        # The MULTI case.
        result = iter(lambda: cursor.fetchmany(chunk_size),
                      self.connection.features.empty_fetchmany_value)  # type: Iterable[Any]
        if not chunked_fetch and not self.connection.features.can_use_chunked_reads:
            # If we are using non-chunked reads, we return the same data
            # structure as normally, but ensure it is all read into memory
            # before going any further. Use chunked_fetch if requested.
            return list(result)
        return result
        # pylint:enable=no-else-return

    def as_sql(self, with_limits=True, with_col_aliases=False
               ) -> Tuple[str, Sequence[Any]]:  # pylint:disable=arguments-differ

        # pylint:disable=too-many-locals,too-many-branches,too-many-statements
        """
        Creates the SQL for this query. Returns the SQL string and list of
        parameters.

        If 'with_limits' is False, any limit/offset information is not included
        in the query.
        """
        # parameter "with_col_aliases" can be a connection instead of bool in Django 1.11
        # (this unexpected type is not before and not after Django 1.11)
        if not isinstance(with_col_aliases, bool):
            assert isinstance(with_col_aliases, salesforce.backend.base.DatabaseWrapper)
            assert not DJANGO_20_PLUS
        # After executing the query, we must get rid of any joins the query
        # setup created. So, take note of alias counts before the query ran.
        # However we do not want to get rid of stuff done in pre_sql_setup(),
        # as the pre_sql_setup will modify query state in a way that forbids
        # another run of it.
        refcounts_before = self.query.alias_refcount.copy()
        try:
            extra_select, order_by, group_by = self.pre_sql_setup()
            soql_trans = self.query_topology()
            if with_limits and self.query.low_mark == self.query.high_mark:
                return '', ()
            if DJANGO_21_PLUS:
                distinct_fields, distinct_params = self.get_distinct()
            else:
                distinct_fields = self.get_distinct()  # type: ignore[assignment] # noqa

            # This must come after 'select', 'ordering', and 'distinct' -- see
            # docstring of get_from_clause() for details.
            from_, f_params = self.get_from_clause()

            where, w_params = self.compile(self.where) if self.where is not None else ("", [])
            having, h_params = self.compile(self.having) if self.having is not None else ("", [])
            params = []
            result = ['SELECT']

            if self.query.distinct:
                if DJANGO_21_PLUS:
                    distinct_result, distinct_params = self.connection.ops.distinct_sql(
                        distinct_fields,
                        distinct_params,
                    )
                    result += distinct_result
                    params += distinct_params
                else:
                    result.append(self.connection.ops.distinct_sql(distinct_fields))

            out_cols = []
            col_idx = 1
            for _, (s_sql, s_params), alias in self.select + extra_select:
                if alias:
                    # fixed by removing 'AS'
                    s_sql = '%s %s' % (s_sql, self.connection.ops.quote_name(alias))
                elif with_col_aliases and not isinstance(with_col_aliases, salesforce.backend.base.DatabaseWrapper):
                    # the check of type "with_col_aliases" is important with ".filter(id__in=queryset)" in Django 1.11
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
                    raise NotSupportedError(
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

            if self.query.model and getattr(self.query.model._meta, 'sf_tooling_api_model', False):
                assert self.query
                result = [x.replace(self.query.model._meta.db_table + '.', '') for x in result]
            return ' '.join(result), tuple(params)
        finally:
            # Finally do cleanup - get rid of the joins we created above.
            self.query.reset_refcounts(refcounts_before)

    def query_topology(self, _alias_map_items: Optional[AliasMapItems] = None) -> Dict[str, str]:
        # pylint:disable=too-many-locals,too-many-branches
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
            # empty alias_map is possible due to field expr in Django 1.8
            return {}
        # Unified interface:
        #   alias_map_items = [(lhs, table, join_cols_, rhs),...]
        query = self.query
        if _alias_map_items:
            alias_map_items = _alias_map_items
        else:
            alias_map_items = []
            for v in query.alias_map.values():
                assert v.table_alias
                if isinstance(v, datastructures.Join):
                    alias_map_items.append((v.parent_alias, v.table_name, v.join_cols, v.table_alias))
                else:
                    alias_map_items.append((None, v.table_name, None, v.table_alias))
        # Analyze
        alias2table = {}  # Dict[str, str]
        side_l, side_r = set(), set()
        for (lhs, table, join_cols_, rhs) in alias_map_items:
            alias2table[rhs] = table
            if lhs is not None:
                assert join_cols_
                (join_cols,) = join_cols_  # length == 1 because primary key is one field
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
        self.root_aliases = list(set(side_l).difference(side_r))
        # self.root_aliases = [x for x in top_lhs_set if alias2table[x] == query.model._meta.db_table]
        # translation rules into SOQL
        soql_trans = {top_lhs: alias2table[top_lhs] for top_lhs in self.root_aliases}
        work_lhses = set(self.root_aliases)
        while work_lhses:
            new_work = set()
            for (lhs, table, join_cols_, rhs) in alias_map_items:
                if lhs is not None:
                    assert join_cols_
                    (join_cols,) = join_cols_
                    if join_cols[0] == 'Id':
                        # swap lhs rhs
                        lhs, rhs = rhs, lhs
                        join_cols = join_cols[1], join_cols[0]
                    if lhs in work_lhses:
                        assert rhs not in soql_trans
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


class SalesforceWhereNode(sql_where.WhereNode):

    # patched "django.db.models.sql.where.WhereNode.as_sql" from Django 1.10, 1.11, 2.0, 2.1
    # pylint:disable=no-else-return,no-else-raise,too-many-branches,too-many-locals,unused-argument
    def as_salesforce(self, compiler: sql_compiler.SQLCompiler, connection) -> Tuple[str, List[Any]]:
        """
        Return the SQL version of the where clause and the value to be
        substituted in. Return '', [] if this node matches everything,
        None, [] if this node is empty, and raise EmptyResultSet if this
        node can't match anything.
        """

        # *** patch 1 (add) begin
        # # prepare SOQL translations
        if not isinstance(compiler, SQLCompiler):
            # future fix for DJANGO_20_PLUS, when deprecated "use_for_related_fields"
            # removed from managers,
            # "str(<UpdateQuery...>)" or "<UpdateQuery...>.get_compiler('default').as_sql()"
            return super(SalesforceWhereNode, self).as_sql(compiler, connection)
        soql_trans = compiler.query_topology()
        # *** patch 1 end

        result = []
        result_params = []  # type: List[Any]
        if self.connector == AND:
            full_needed, empty_needed = len(self.children), 1
        else:
            full_needed, empty_needed = 1, len(self.children)

        for child in self.children:
            try:
                sql, params = compiler.compile(child)
            except EmptyResultSet:
                empty_needed -= 1
            else:
                if sql:

                    # *** patch 2 (add) begin
                    # # translate the alias of child to SOQL name
                    x_match = re.match(r'(\w+)\.(.*)', sql)
                    if x_match:
                        x_table, x_field = x_match.groups()
                        sql = '%s.%s' % (soql_trans[x_table], x_field)
                        # print('sql params:', sql, params)
                    # *** patch 2 end

                    result.append(sql)
                    result_params.extend(params)
                else:
                    full_needed -= 1
            # Check if this node matches nothing or everything.
            # First check the amount of full nodes and empty nodes
            # to make this node empty/full.
            # Now, check if this node is full/empty using the
            # counts.
            if empty_needed == 0:
                if self.negated:
                    return '', []
                else:
                    raise EmptyResultSet
            if full_needed == 0:
                if self.negated:
                    raise EmptyResultSet
                else:
                    return '', []
        conn = ' %s ' % self.connector
        sql_string = conn.join(result)
        if sql_string:
            if self.negated:
                # *** patch 3 (remove) begin
                # # Some backends (Oracle at least) need parentheses
                # # around the inner SQL in the negated case, even if the
                # # inner SQL contains just a single expression.
                # sql_string = 'NOT (%s)' % sql_string
                # *** patch 3 (add)
                # SOQL requires parentheses around "NOT" expression, if combined with AND/OR
                sql_string = '(NOT (%s))' % sql_string
                # *** patch 3 end

            # *** patch 4 (combine two versions into one compatible) begin
            # elif len(result) > 1:                                    # Django 1.11
            # elif len(result) > 1 or self.resolved:                   # Django 2.0, 2.1
            elif len(result) > 1 or getattr(self, 'resolved', False):  # compatible code
                # *** patch 4 end

                sql_string = '(%s)' % sql_string
        return sql_string, result_params
    # pylint:enable=no-else-return,too-many-branches,too-many-locals,unused-argument


class SQLInsertCompiler(sql_compiler.SQLInsertCompiler, SQLCompiler):  # type: ignore[misc] # noqa # as_sql
    if DJANGO_31_PLUS:

        def execute_sql(self, returning_fields=None):
            # copied from Django 3.1, with one line patch
            assert not (
                returning_fields and len(self.query.objs) != 1 and
                not self.connection.features.can_return_rows_from_bulk_insert
            )
            self.returning_fields = returning_fields
            with self.connection.cursor() as cursor:
                # this line is the added patch:
                cursor.prepare_query(self.query)
                for sql, params in self.as_sql():
                    cursor.execute(sql, params)
                if not self.returning_fields:
                    return []
                if self.connection.features.can_return_rows_from_bulk_insert and len(self.query.objs) > 1:
                    return self.connection.ops.fetch_returned_insert_rows(cursor)
                if self.connection.features.can_return_columns_from_insert:
                    assert len(self.query.objs) == 1
                    return [self.connection.ops.fetch_returned_insert_columns(cursor, self.returning_params)]
                return [(self.connection.ops.last_insert_id(
                    cursor, self.query.get_meta().db_table, self.query.get_meta().pk.column
                ),)]

    elif DJANGO_30_PLUS:

        def execute_sql(self, returning_fields=None):
            # copied from Django 3.0, with one line patch
            assert not (
                returning_fields and len(self.query.objs) != 1 and
                not self.connection.features.can_return_rows_from_bulk_insert
            )
            self.returning_fields = returning_fields
            with self.connection.cursor() as cursor:
                # this line is the added patch:
                cursor.prepare_query(self.query)
                for sql, params in self.as_sql():
                    cursor.execute(sql, params)
                if not self.returning_fields:
                    return []
                if self.connection.features.can_return_rows_from_bulk_insert and len(self.query.objs) > 1:
                    return self.connection.ops.fetch_returned_insert_rows(cursor)
                if self.connection.features.can_return_columns_from_insert:
                    if (
                            len(self.returning_fields) > 1 and
                            not self.connection.features.can_return_multiple_columns_from_insert
                    ):
                        raise NotSupportedError(
                            'Returning multiple columns from INSERT statements is '
                            'not supported on this database backend.'
                        )
                    assert len(self.query.objs) == 1
                    return self.connection.ops.fetch_returned_insert_columns(cursor)
                return [self.connection.ops.last_insert_id(
                    cursor, self.query.get_meta().db_table, self.query.get_meta().pk.column
                )]

    else:

        def execute_sql(self, return_id=False):  # type: ignore[misc] # noqa # check typing only for Django >= 3.0
            # copied from Django 1.11, with one line patch
            assert not (
                return_id and len(self.query.objs) != 1 and
                not self.connection.features.can_return_ids_from_bulk_insert
            )
            self.return_id = return_id
            with self.connection.cursor() as cursor:
                # this line is the added patch:
                cursor.prepare_query(self.query)
                for sql, params in self.as_sql():
                    cursor.execute(sql, params)
                if not (return_id and cursor):
                    return
                if self.connection.features.can_return_ids_from_bulk_insert and len(self.query.objs) > 1:
                    return self.connection.ops.fetch_returned_insert_ids(cursor)
                if self.connection.features.can_return_id_from_insert:
                    assert len(self.query.objs) == 1
                    return self.connection.ops.fetch_returned_insert_id(cursor)
                return self.connection.ops.last_insert_id(
                    cursor, self.query.get_meta().db_table, self.query.get_meta().pk.column
                )


class SQLDeleteCompiler(sql_compiler.SQLDeleteCompiler, SQLCompiler):  # type: ignore[misc] # noqa # as_sql
    pass


class SQLUpdateCompiler(sql_compiler.SQLUpdateCompiler, SQLCompiler):  # type: ignore[misc] # noqa # as_sql,execute_sql
    pass


class SQLAggregateCompiler(sql_compiler.SQLAggregateCompiler, SQLCompiler):  # type: ignore[misc] # noqa # as_sql
    pass
