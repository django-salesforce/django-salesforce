from collections import OrderedDict
import re

from django.core.management.commands.inspectdb import Command as InspectDBCommand
from django.db import connections
from six import PY3, text_type
from salesforce.backend import introspection as sf_introspection


def fix_field_params_repr(params):
    """
    Fixes repr() of "field_params" for Python 2 with future text_type_literals.
    """
    class ReprUnicode(text_type):
        def __new__(cls, text):
            return text_type.__new__(cls, text)

        def __repr__(self):
            out = repr(text_type(self))
            return out[1:] if out.startswith("u'") or out.startswith('u"') else out

    class ReprChoices(list):
        def __new__(cls, choices):
            return list.__new__(cls, choices)

        def __repr__(self):
            out = []
            for x_0, x_1 in self:
                out.append('(%s, %s)' % (
                    repr(ReprUnicode(x_0) if isinstance(x_0, text_type) else x_0),
                    repr(ReprUnicode(x_1) if isinstance(x_1, text_type) else x_1)
                ))
            return '[%s]' % (', '.join(out))
    if PY3:
        return params
    out = OrderedDict()
    for k, v in params.items():
        if k == 'choices' and v:
            v = ReprChoices(v)
        elif isinstance(v, text_type):
            v = ReprUnicode(v)
        out[k] = v
    return out


def fix_international(text):
    "Fix excaped international characters back to utf-8"
    class SmartInternational(str):
        def __new__(cls, text):
            return str.__new__(cls, text)

        def endswith(self, string):
            return super(SmartInternational, self).endswith(str(string))
    if PY3:
        return text
    out = []
    last = 0
    for match in re.finditer(r'(?<=[^\\])(?:\\x[0-9a-f]{2}|\\u[0-9a-f]{4})', text):
        start, end, group = match.start(), match.end(), match.group()
        out.append(text[last:start])
        c = group.decode('unicode_escape')
        out.append(c if ord(c) > 160 and ord(c) != 173 else group)
        last = end
    out.append(text[last:])
    return SmartInternational(''.join(out).encode('utf-8'))


class Command(InspectDBCommand):

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument('--table-filter', action='store', dest='table_name_filter',
                            help='Regular expression that filters API Names of SF tables to introspect.')

    def handle(self, **options):
        if isinstance(options['table_name_filter'], str):
            options['table_name_filter'] = re.compile(options['table_name_filter']).match
        self.verbosity = int(options['verbosity'])          # pylint:disable=attribute-defined-outside-init
        self.connection = connections[options['database']]  # pylint:disable=attribute-defined-outside-init
        if self.connection.vendor == 'salesforce':
            if not PY3:
                self.stdout.write("# coding: utf-8\n")
            self.db_module = 'salesforce'
            for line in self.handle_inspection(options):
                line = line.replace(" Field renamed because it contained more than one '_' in a row.", "")
                line = re.sub(' #$', '', line)
                self.stdout.write(fix_international("%s\n" % line))
        else:
            super(Command, self).handle(**options)

    def get_field_type(self, connection, table_name, row):
        field_type, field_params, field_notes = (super(Command, self)
                                                 .get_field_type(connection, table_name, row))
        if connection.vendor == 'salesforce':
            if 'ref_comment' in row.params:
                field_notes.append(row.params.pop('ref_comment'))
            field_params.update(row.params)
        return field_type, fix_field_params_repr(field_params), field_notes

    def normalize_col_name(self, col_name, used_column_names, is_relation):
        if self.connection.vendor == 'salesforce':
            beautified = re.sub('__c$', '', col_name)
            beautified = re.sub(r'([a-z0-9])(?=[A-Z])', r'\1_', beautified)
            beautified = beautified.lower()
            new_name, field_params, field_notes = (super(Command, self)
                                                   .normalize_col_name(beautified, used_column_names, is_relation))
            # *reconstructed* : is what will SfField reconstruct to db column
            field_params = OrderedDict(sorted(field_params.items()))
            reconstructed = new_name.title().replace('_', '')
            if col_name.endswith('__c'):
                reconstructed += '__c'
                field_params['custom'] = True
            elif is_relation:
                reconstructed += 'Id'
            # TODO: Discuss: Maybe 'db_column' can be compared case insensitive,
            #       but exact compare is safer.
            if reconstructed != col_name or self.verbosity >= 2:
                field_params['db_column'] = col_name
            else:
                field_params.pop('db_column', None)
            if is_relation:
                if col_name in sf_introspection.last_with_important_related_name:
                    field_params['related_name'] = '%s_%s_set' % (
                        sf_introspection.last_introspected_model.lower(),
                        new_name.replace('_', '')
                    )
                if col_name in sf_introspection.last_read_only:
                    field_params['sf_read_only'] = sf_introspection.last_read_only[col_name]
                reference_to, relationship_order = sf_introspection.last_refs[col_name]
                if len(reference_to) > 1:
                    field_notes.append('Reference to tables [%s]' % (', '.join(reference_to)))
                if relationship_order is not None:
                    # 0 = primary relationship, 1 = secondary relationship, * = any cascade delete
                    field_notes.append('Master Detail Relationship %s' % relationship_order)
        else:
            new_name, field_params, field_notes = (super(Command, self)
                                                   .normalize_col_name(col_name, used_column_names, is_relation))
        return new_name, fix_field_params_repr(field_params), field_notes

    # the parameter 'is_view' has been since Django 2.1 and 'is_partition' since Django 2.2
    def get_meta(self, table_name, constraints=None, column_to_field_name=None, is_view=False, is_partition=None):
        """
        Return a sequence comprising the lines of code necessary
        to construct the inner Meta class for the model corresponding
        to the given database table name.
        """
        # pylint:disable=arguments-differ,too-many-arguments,unused-argument
        meta = ["    class Meta(models.Model.Meta):",
                "        db_table = '%s'" % table_name]
        if self.connection.vendor == 'salesforce':
            for line in self.connection.introspection.get_additional_meta(table_name):
                meta.append("        " + line)
        meta.append("")
        return meta
