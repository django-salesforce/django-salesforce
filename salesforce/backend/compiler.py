from django.db.models.sql import compiler

class SQLCompiler(compiler.SQLCompiler):
	def get_columns(self, with_aliases=False):
		cols = compiler.SQLCompiler.get_columns(self, with_aliases)
		return [x.split('.')[1].strip('"') for x in cols]
	
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
			if(name.startswith('salesforce_')):
				name = name[11:]
				name = ''.join([x.capitalize() for x in name.split('_')])
			connector = not first and ', ' or ''
			result.append('%s%s' % (connector, name))
			first = False
		return result, []

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
