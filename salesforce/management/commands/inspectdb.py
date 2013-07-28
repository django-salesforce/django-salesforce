from django.core.management.commands.inspectdb import Command as InspectDBCommand

class Command(InspectDBCommand):
	db_module = 'salesforce'

	def get_field_type(self, connection, table_name, row):
		field_type, field_params, field_notes = super(Command, self).get_field_type(connection, table_name, row)
		if connection.alias == 'salesforce':
			name, type_code, display_size, internal_size, precision, scale, null_ok, sf_params = row
			field_params.update(sf_params)
		return field_type, field_params, field_notes
