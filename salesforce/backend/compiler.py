from django.db.models.sql import compiler, query, where

def process_column(name):
	if(name.startswith('salesforce_')):
		name = name[11:]
		name = ''.join([x.capitalize() for x in name.split('_')])
	return name

class SQLCompiler(compiler.SQLCompiler):
	def get_columns(self, with_aliases=False):
		cols = compiler.SQLCompiler.get_columns(self, with_aliases)
		result = []
		for col in cols:
			if('.' in col):
				name = col.split('.')[1]
			else:
				name = col
			result.append(name.strip('"'))
		return result
	
	def get_from_clause(self):
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
			#TODO: change this so the right stuff just ends up in alias_map
			name = process_column(name)
			connector = not first and ', ' or ''
			result.append('%s%s' % (connector, name))
			first = False
		return result, []
	
	def quote_name_unless_alias(self, name):
		"""
		A wrapper around connection.ops.quote_name that doesn't quote aliases
		for table names. This avoids problems with some SQL dialects that treat
		quoted strings specially (e.g. PostgreSQL).
		"""
		name = process_column(name)
		r = self.connection.ops.quote_name(name)
		self.quote_cache[name] = r
		return r


class SalesforceWhereNode(where.WhereNode):
	def sql_for_columns(self, data, qn, connection):
		"""
		Returns the SQL fragment used for the left-hand side of a column
		constraint (for example, the "T1.foo" portion in the clause
		"WHERE ... T1.foo = 6").
		"""
		table_alias, name, db_type = data
		return connection.ops.field_cast_sql(db_type) % name

class SQLInsertCompiler(compiler.SQLInsertCompiler, SQLCompiler):
	pass

class SQLDeleteCompiler(compiler.SQLDeleteCompiler, SQLCompiler):
	pass

class SQLUpdateCompiler(compiler.SQLUpdateCompiler, SQLCompiler):
	pass

class SQLAggregateCompiler(compiler.SQLAggregateCompiler, SQLCompiler):
	pass

class SQLDateCompiler(compiler.SQLDateCompiler, SQLCompiler):
	pass
