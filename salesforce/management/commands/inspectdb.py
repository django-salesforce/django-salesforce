from collections import OrderedDict
from typing import Any, Container, Dict, List, Mapping, Tuple
import argparse
import re

from django.core.management.commands.inspectdb import Command as InspectDBCommand
from django.db import connections
from salesforce.backend import introspection as sf_introspection


class Command(InspectDBCommand):

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('--concise-db-column', action='store_true', dest='concise_db_column',
                            help="Export 'db_column' only if it is necessary and can not be reconstructed "
                            "from the name or 'custom'")
        parser.add_argument('--table-filter', action='store', dest='table_name_filter',
                            help='Regular expression that filters API Names of SF tables to introspect.')
        parser.add_argument('--tooling-api', action='store_true',
                            # help="Introspect metadata models in Tooling API (not standard tables)",
                            help=argparse.SUPPRESS,  # hidden option
                            )


    def handle(self, **options: Any) -> None:  # type: ignore[override] # noqa # it is incompatible in Django
        if isinstance(options['table_name_filter'], str):
            options['table_name_filter'] = re.compile(options['table_name_filter']).match
        self.verbosity = int(options['verbosity'])          # pylint:disable=attribute-defined-outside-init
        self.connection = connections[options['database']]  # pylint:disable=attribute-defined-outside-init
        self.concise_db_column = options['concise_db_column']  # pylint:disable=attribute-defined-outside-init
        self.tooling_api = options['tooling_api']

        if self.connection.vendor == 'salesforce':
            connection = connections[options['database']]
            connection.introspection.is_tooling_api = self.tooling_api

            self.db_module = 'salesforce'
            for line in self.handle_inspection(options):
                line = line.replace(" Field renamed because it contained more than one '_' in a row.", "")
                line = re.sub(' #$', '', line)
                self.stdout.write("%s\n" % line)
        else:
            super(Command, self).handle(**options)

    def get_field_type(self, connection, table_name, row):
        field_type, field_params, field_notes = (super(Command, self)
                                                 .get_field_type(connection, table_name, row))
        if connection.vendor == 'salesforce':
            if 'ref_comment' in row.params:
                field_notes.append(row.params.pop('ref_comment'))
            field_params.update(row.params)
        return field_type, field_params, field_notes

    def normalize_col_name(self, col_name: str, used_column_names: Container[str], is_relation: bool
                           ) -> Tuple[str, Mapping[str, Any], List[str]]:
        if self.connection.vendor == 'salesforce':
            beautified = re.sub('__c$', '', col_name)
            beautified = re.sub(r'([a-z0-9])(?=[A-Z])', r'\1_', beautified)
            beautified = beautified.lower()
            new_name, field_params, field_notes = (
                super().normalize_col_name(beautified, used_column_names, is_relation)
            )
            # *reconstructed* : is what will SfField reconstruct to db column
            field_params = OrderedDict(sorted(field_params.items()))
            reconstructed = new_name.title().replace('_', '')
            if col_name.endswith('__c'):
                reconstructed += '__c'
                if self.concise_db_column:
                    field_params['custom'] = True
            elif is_relation:
                reconstructed += 'Id'
            # TODO: Discuss: Maybe 'db_column' can be compared case insensitive,
            #       but exact compare is safer.
            if reconstructed != col_name or not self.concise_db_column:
                field_params['db_column'] = col_name
            else:
                field_params.pop('db_column', None)
            if is_relation:
                last_introspection = sf_introspection.last_introspection
                assert last_introspection
                if col_name in last_introspection.important_related_names:
                    field_params['related_name'] = '%s_%s_set' % (
                        last_introspection.model_name.lower(),
                        new_name.replace('_', '')
                    )
                fields_map = last_introspection.fields_map[col_name].copy()
                reference_to, relationship_order = fields_map.pop('refs')
                if len(reference_to) > 1:
                    field_notes.append('Reference to tables [%s]' % (', '.join(reference_to)))
                if relationship_order is not None:
                    # 0 = primary relationship, 1 = secondary relationship, * = any cascade delete
                    field_notes.append('Master Detail Relationship %s' % relationship_order)
                field_params.update(fields_map)
        else:
            new_name, field_params, field_notes = (super(Command, self)
                                                   .normalize_col_name(col_name, used_column_names, is_relation))
        return new_name, field_params, field_notes

    # the parameter 'is_view' has been since Django 2.1 and 'is_partition' since Django 2.2
    def get_meta(self, table_name: str, constraints: Any = None, column_to_field_name: Dict[str, str] = None,
                 is_view: bool = False, is_partition: bool = False) -> List[str]:
        """
        Return a sequence comprising the lines of code necessary
        to construct the inner Meta class for the model corresponding
        to the given database table name.
        """
        # pylint:disable=arguments-differ,too-many-arguments,unused-argument
        meta = ["    class Meta(models.Model.Meta):",
                "        db_table = '%s'" % table_name]
        if self.tooling_api:
            meta.append("        managed = False")
            meta.append("        sf_tooling_api_model = True")
        if self.connection.vendor == 'salesforce':
            for line in self.connection.introspection.get_additional_meta(table_name):
                meta.append("        " + line)
        meta.append("")
        return meta
