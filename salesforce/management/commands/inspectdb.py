from django.core.management.commands.inspectdb import Command as InspectDBCommand
import re
import salesforce

class Command(InspectDBCommand):

	def handle_noargs(self, **options):
		self._database = options.get('database', 'default')
		try:
			for line in self.handle_inspection(options):
				self.stdout.write("%s\n" % line)
		except NotImplementedError:
			raise CommandError("Database inspection isn't supported for the currently selected database backend.")

	@property
	def db_module(self):
		return 'salesforce' if self._database == 'salesforce' else super(Command, self).db_module


	def get_field_type(self, connection, table_name, row):
		field_type, field_params, field_notes = super(Command, self).get_field_type(connection, table_name, row)
		if connection.alias == 'salesforce':
			name, type_code, display_size, internal_size, precision, scale, null_ok, sf_params = row
			field_params.update(sf_params)
		return field_type, field_params, field_notes

	def normalize_col_name(self, col_name, used_column_names, is_relation):
		new_name, field_params, field_notes = super(Command, self).normalize_col_name(col_name, used_column_names, is_relation)
		if self.db_module == 'salesforce':
			if is_relation:
				if col_name.lower().endswith('_id'):
					field_params['db_column'] = col_name[:-3] + col_name[-2:]
				field_params['related_name'] = ('%s_%s_set' % (
					salesforce.backend.introspection.last_introspected_model,
					re.sub('_Id$', '', new_name).replace('_', '')
					)).lower()
			field_notes = [x for x in field_notes if x != 'Field name made lowercase.']
		return new_name, field_params, field_notes
