# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Generate queries using the SOQL dialect.
"""
from django.db.models.sql import compiler, query, where, constants
from django.db.models.sql.datastructures import EmptyResultSet

import django
from pkg_resources import parse_version
DJANGO_14 = (parse_version(django.get_version()) >= parse_version('1.4'))
DJANGO_16 = django.VERSION[:2] >= (1,6)

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
		result = []
		for col in cols:
			if('.' in col):
				name = col.split('.')[1]
			else:
				name = col
			result.append(name.strip('"'))
		return (result, col_params) if DJANGO_16 else result
	
	def get_from_clause(self):
		"""
		Return the FROM clause, converted the SOQL dialect.
		"""
		result = []
		first = True
		for alias in self.query.tables:
			if not self.query.alias_refcount[alias]:
				continue
			try:
				name, alias, join_type, lhs, lhs_col, col, nullable = self.query.alias_map[alias]
			except KeyError:
				# Extra tables can end up in self.tables, but not in the
				# alias_map if they aren't in a join. That's OK. We skip them.
				continue
			connector = not first and ', ' or ''
			result.append('%s%s' % (connector, name))
			first = False
		return result, []
	
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
		
		if not result_type:
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
	
	def sql_for_columns(self, data, qn, connection, internal_type=None):  # Fixed for Django 1.6
		"""
		Don't attempt to quote column names.
		"""
		table_alias, name, db_type = data
		if DJANGO_16:
			return connection.ops.field_cast_sql(db_type, internal_type) % name
		else:
			return connection.ops.field_cast_sql(db_type) % name

	def make_atom(self, child, qn, connection):
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

class SQLInsertCompiler(compiler.SQLInsertCompiler, SQLCompiler):
	if(DJANGO_14):
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
