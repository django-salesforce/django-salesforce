# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Generate queries using the SOQL dialect.
"""
from django.db import models
from django.db.models.sql import compiler, query, where, constants, AND, OR
from django.db.models.sql.datastructures import EmptyResultSet

from salesforce import DJANGO_15, DJANGO_16, DJANGO_17_PLUS


def process_name(name):
	"""
	Convert a Djangofied column name into a Salesforce-compliant column name.

	TODO: this is sketchy
	"""
	if(name.startswith('example_')):
		name = name[8:]
		name = ''.join([x.capitalize() for x in name.split('_')])
	return name

class SQLCompiler(compiler.SQLCompiler):
	"""
	A subclass of the default SQL compiler for the SOQL dialect.
	"""
	def resolve_columns(self, row, fields):
		# TODO @hynekcer: Create class salesforce.fields.ForeignKey with customized
		#      get_attname method where "_id" is replaced by "Id".
		#      Then no db_column='....Id" in models will be necessary and
		#      this method can be also removed
		result = []
		for field in fields:
			result.append(row[field.column])
		return result

	def get_columns(self, with_aliases=False):
		"""
		Remove table names and strip quotes from column names.
		"""
		if DJANGO_16:
			cols, col_params = compiler.SQLCompiler.get_columns(self, with_aliases)
		else:
			cols = compiler.SQLCompiler.get_columns(self, with_aliases)
		result = [x.replace(' AS ', ' ') for x in cols]
		#result = []
		#for col in cols:
		#	if('.' in col):
		#		name = col.split('.')[1]
		#	else:
		#		name = col
		#	result.append(name.strip('"'))
		return (result, col_params) if DJANGO_16 else result

	def get_from_clause(self):
		"""
		Return the FROM clause, converted the SOQL dialect.

		It should be only the name of base object, even in parent-to-child and
		child-to-parent relationships queries.
		"""
		for alias in self.query.tables:
			if self.query.alias_refcount[alias]:
				try:
					name, alias, join_type, lhs, lhs_col, col, nullable = self.query.alias_map[alias]
				except KeyError:
					# Extra tables can end up in self.tables, but not in the
					# alias_map if they aren't in a join. That's OK. We skip them.
					continue
				return [name], []
		raise AssertionError("At least one table should be referenced in the query.")

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

		ordering_aliases = self.ordering_aliases if DJANGO_16 else self.query.ordering_aliases
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


class SalesforceWhereNode(where.WhereNode):
	overridden_types = ['isnull']

	# Simple related fields work only without this, but for more complicated
	# cases this must be fixed and re-enabled.
	#def sql_for_columns(self, data, qn, connection, internal_type=None):  # Fixed for Django 1.6
	#	"""
	#	Don't attempt to quote column names.
	#	"""
	#	table_alias, name, db_type = data
	#	if DJANGO_16:
	#		return connection.ops.field_cast_sql(db_type, internal_type) % name
	#	else:
	#		return connection.ops.field_cast_sql(db_type) % name

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

	DJANGO_14_EXACT = not DJANGO_15
	if DJANGO_14_EXACT:
		# patched "django.db.models.sql.where.WhereNode.as_sql" from Django 1.4
		def as_sql(self, qn, connection):
			"""
			Returns the SQL version of the where clause and the value to be
			substituted in. Returns None, None if this node is empty.

			If 'node' is provided, that is the root of the SQL generation
			(generally not needed except by the internal implementation for
			recursion).
			"""
			if not self.children:
				return None, []
			result = []
			result_params = []
			empty = True
			for child in self.children:
				try:
					if hasattr(child, 'as_sql'):
						sql, params = child.as_sql(qn=qn, connection=connection)
					else:
						# A leaf node in the tree.
						sql, params = self.make_atom(child, qn, connection)

				except EmptyResultSet:
					if self.connector == AND and not self.negated:
						# We can bail out early in this particular case (only).
						raise
					elif self.negated:
						empty = False
					continue
				except models.sql.datastructures.FullResultSet:
					if self.connector == OR:
						if self.negated:
							empty = True
							break
						# We match everything. No need for any constraints.
						return '', []
					if self.negated:
						empty = True
					continue

				empty = False
				if sql:
					result.append(sql)
					result_params.extend(params)
			if empty:
				raise EmptyResultSet

			conn = ' %s ' % self.connector
			sql_string = conn.join(result)
			if sql_string:
				if self.negated:
					# patch begin
					# SOQL requires parentheses around "NOT" if combined with AND/OR
					# sql_string = 'NOT (%s)' % sql_string
					sql_string = '(NOT (%s))' % sql_string
					# patch end
				elif len(self.children) != 1:
					sql_string = '(%s)' % sql_string
			return sql_string, result_params
	else:
		# patched "django.db.models.sql.where.WhereNode.as_sql" from Django 1.5, 1.6., 1.74
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
			result = []
			result_params = []
			everything_childs, nothing_childs = 0, 0
			non_empty_childs = len(self.children)

			for child in self.children:
				try:
					if hasattr(child, 'as_sql'):
						# patch begin (combined Django 1,5, 1.6, 1.7)
						if DJANGO_17_PLUS:
							sql, params = qn.compile(child)
						else:
							sql, params = child.as_sql(qn=qn, connection=connection)
						# patch end
					else:
						# A leaf node in the tree.
						sql, params = self.make_atom(child, qn, connection)
				except EmptyResultSet:
					nothing_childs += 1
				else:
					if sql:
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

	if DJANGO_17_PLUS:
		def add(self, data, conn_type, **kwargs):
			cond = isinstance(data, models.lookups.IsNull) and not isinstance(data, IsNull)
			if cond:
				# "lhs" and "rhs" means Left and Right Hand Side of an condition
				data = IsNull(data.lhs, data.rhs)
			return super(SalesforceWhereNode, self).add(data, conn_type, **kwargs)

		as_salesforce = as_sql
		del as_sql


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

class SQLDateCompiler(compiler.SQLDateCompiler, SQLCompiler):
	pass


# Lookups
if DJANGO_17_PLUS:
	class IsNull(models.Field.get_lookup(models.Field(), 'isnull')):
		# The expected result base class above is `models.lookups.IsNull`.
		lookup_name = 'isnull'

		def as_sql(self, qn, connection):
			if connection.vendor == 'salesforce':
				sql, params = qn.compile(self.lhs)
				return ('%s %s null' % (sql, ('=' if self.rhs else '!='))), params
			else:
				return super(IsNull, self).as_sql(qn, connection)

	models.Field.register_lookup(IsNull)
