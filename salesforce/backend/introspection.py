# django-salesforce
#
# by Hyneck Cernoch and Phil Christensen
# See LICENSE.md for details
#

"""
Salesforce introspection code.  (like django.db.backends.*.introspection)
"""

import json
import logging
import re
from collections import OrderedDict, namedtuple
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from django.conf import settings
from django.db.backends.base.introspection import (
    BaseDatabaseIntrospection, FieldInfo as BaseFieldInfo, TableInfo,
)
from django.utils.text import camel_case_to_spaces
from django.db.backends.utils import CursorWrapper as _Cursor  # for typing

from salesforce.backend import DJANGO_22_PLUS, DJANGO_32_PLUS, DJANGO_50_PLUS
import salesforce.fields

log = logging.getLogger(__name__)

FieldInfo = namedtuple(  # type: ignore[misc]
    'FieldInfo',
    'name type_code display_size internal_size precision scale null_ok default'
    + (' collation' if DJANGO_32_PLUS else '') +
    ' params'  # the last name 'params' is our extension for Salesforce
)
assert FieldInfo._fields[:-1] == BaseFieldInfo._fields

# these sObjects are not tables - ignore them
# not queryable, not searchable, not retrieveable, only triggerable
PROBLEMATIC_OBJECTS = [
    'AssetTokenEvent',  # new in API 39.9 Spring '17
    'OrgLifecycleNotification',  # new in API 40.0 Summer '17
    'BatchApexErrorEvent',  # new in API 44.0 Winter '19
    'PlatformStatusAlertEvent',  # new in API 45.0 Spring '19
    'LogoutEventStream',  # new in API 46.0 Summer '19
    'AsyncOperationEvent',  # new in API 46.0 Summer '19
    'AsyncOperationStatus',  # new in API 46.0 Summer '19
    'FlowExecutionErrorEvent',  # new in API 47.0 Winter '20 - missing 'Id'
    'FlowOrchestrationEvent',  # new in API 53.0 Winter '22
    'DataObjectDataChgEvent',  # new in API 55.0 Summer '22 (no 'Id' field)
    'OrgSharingEvent', 'StatsInvalidationEvent',  # new in API 59.0 Summer '24 (no 'Id' field)
    'EmailBounceEvent',  # new in API 60.0 Spring '24 (no 'Id' field)
    'MLEngagementEvent',  # new in API 61.0 Summer '24 (no 'Id' field)
    'EvaluationJobResultEvent',  # new in API 62.0 Winter '25 (no 'Id' field)
]

# this global variable is for `salesforce.management.commands.inspectdb`
last_introspection = None


class LastIntrospection:
    def __init__(self, model_name: str, important_related_names: List[str],
                 fields_map: Dict[str, Dict[str, Any]]) -> None:
        self.model_name = model_name
        self.important_related_names = important_related_names
        self.fields_map = fields_map


class DatabaseIntrospection(BaseDatabaseIntrospection):
    """
    The most comfortable and complete output is by:
        table_list_cache:               property with database and tables attributes
        table_description_cache(name):  method   with table and fields attributes
    Everything is with caching the results for the next use.
    Other methods are very customized with hooks for
    by django.core.management.commands.inspectdb
    """

    data_types_reverse = {
        'base64':                         'TextField',
        'boolean':                        'BooleanField',
        'byte':                           'SmallIntegerField',
        'date':                           'DateField',
        'datetime':                       'DateTimeField',
        'double':                         'DecimalField',
        'float':                          'FloatField',  # specially not to Decimal; used in tooling metadata
        'int':                            'IntegerField',
        'string':                         'CharField',
        'time':                           'TimeField',
        'anyType':                        'CharField',
        'calculated':                     'CharField',
        'combobox':                       'CharField',
        'currency':                       'DecimalField',
        'datacategorygroupreference':     'CharField',
        'email':                          'EmailField',
        'encryptedstring':                'CharField',
        'id':                             'AutoField',
        'masterrecord':                   'CharField',
        # multipicklist can be implemented by a descendant with a special validator + widget
        'multipicklist':                  'CharField',
        'percent':                        'DecimalField',
        'phone':                          'CharField',
        # picklist is ('CharField', {'choices': (...)})
        'picklist':                       'CharField',
        'reference':                      'ForeignKey',
        'textarea':                       'TextField',
        'url':                            'URLField',
        'complexvalue':                   'XJSONField',
    }

    def __init__(self, conn: Any) -> None:
        BaseDatabaseIntrospection.__init__(self, conn)
        self._table_names: Set[str] = set()
        self._table_list_cache = None  # type: Optional[Dict[str, Any]]
        self._table_description_cache = {}  # type: Dict[str, Dict[str, Any]]
        self._converted_lead_status = None  # type: Optional[str]
        self.is_tooling_api = False  # modified by other modules

    # -- custom methods

    def filter_table_list(self, table_names: Iterable[str]):
        # value "self._table_list_cache" is never None after avaluating the property "self.table_list_cache"
        assert self.table_list_cache and self._table_list_cache
        self._table_list_cache['sobjects'] = [
            x for x in self.table_list_cache['sobjects'] if x['name'] in table_names
        ]
        self._table_names = self._table_names.intersection(table_names)
        unknown_tables = [x for x in table_names if x not in self.connection.introspection._table_names]  # noqa pylint:disable=protected-access
        if unknown_tables:
            raise ValueError('These tables are not a part of the inspected Salesforce database: '
                             '{}'.format(unknown_tables))

    def reset_table_list(self) -> None:
        self._table_list_cache = None
        self.table_list_cache  # pylint:disable=pointless-statement

    @property
    def sobjects_prefix(self) -> str:
        return 'sobjects' if not self.is_tooling_api else 'tooling/sobjects'

    @property
    def table_list_cache(self) -> Dict[str, Any]:
        if self._table_list_cache is None:
            log.debug('Request API URL: GET sobjects')
            if not self.connection.connection:
                self.connection.connect()
            response = self.connection.connection.handle_api_exceptions('GET', self.sobjects_prefix + '/')
            # charset is detected from headers by requests package
            self._table_list_cache = response.json(object_pairs_hook=OrderedDict)
            self._table_list_cache['sobjects'] = [
                x for x in self._table_list_cache['sobjects']
                if x['name'] not in PROBLEMATIC_OBJECTS and not x['name'].endswith('ChangeEvent')
            ]
            self._table_names = {x['name'] for x in self._table_list_cache['sobjects']}
        return self._table_list_cache

    def table_description_cache(self, table: str) -> Dict[str, Any]:
        if table not in self._table_description_cache:
            if table == 'django_migrations':
                raise ValueError("The internal table 'django_migrations' is not a normal Model.")
            log.debug('Request API URL: GET sobjects/%s/describe', table)
            response = self.connection.connection.handle_api_exceptions('GET', self.sobjects_prefix, table, 'describe/'
                                                                        )
            self._table_description_cache[table] = response.json(object_pairs_hook=OrderedDict)
            field_list = self._table_description_cache[table]['fields']
            # 'Id' field is sometimes not the first field in tooling metadata SObjects
            id_fields = [x for x in field_list if x['name'] == 'Id']
            assert len(id_fields) == 1, "Table {!r} must contain one field named 'Id'".format(table)
            id_field, = id_fields
            assert id_field['type'] == 'id', (
                "Invalid type of the field 'Id' in table '{}'".format(table))
            del field_list[field_list.index(id_field)]
        return self._table_description_cache[table]

    # -- standard methods

    if DJANGO_22_PLUS:

        def identifier_converter(self, name: str) -> str:
            """A conversion to the identifier for the purposes of comparison."""
            return name.lower()

    else:

        def table_name_converter(self, name: str) -> str:  # pylint:disable=no-self-use
            return name.lower()

        def column_name_converter(self, name: str) -> str:  # pylint:disable=no-self-use
            return name.lower()

    def get_table_list(self, cursor: _Cursor) -> List[TableInfo]:
        "Returns a list of table names in the current database."
        result = [TableInfo(SfProtectName(x['name']), 't') for x in self.table_list_cache['sobjects']]
        return result

    # -- custom methods

    def get_field_names(self, table_name: str) -> List[str]:
        return [x['name'] for x in self.table_description_cache(table_name)['fields']]

    def get_field_params(self, field: Dict[str, Any]) -> Dict[str, Any]:  # pylint:disable=too-many-branches
        params = OrderedDict()
        if field['label'] and field['label'] != camel_case_to_spaces(re.sub('__c$', '', field['name'])).title():
            params['verbose_name'] = field['label']
        if not field['updateable'] or not field['createable']:
            # Fields that are result of a formula or system fields modified
            # by triggers or by other apex code
            # use symbolic names NOT_UPDATEABLE, NOT_CREATABLE, READ_ONLY instead of 1, 2, 3
            sf_read_only = (0 if field['updateable'] else 1) | (0 if field['createable'] else 2)
            params['sf_read_only'] = reverse_models_names[sf_read_only]

        if field['defaultValue'] is not None:
            default: Optional[SymbolicModelsName] = field['defaultValue']
        elif field['defaultValueFormula']:
            if re.match(r'^(?:(?:-?[0-9]+(?:\.[0-9]+)?)|(?:"(?:[^"]|\")*"))$', field['defaultValueFormula']):
                # (int, float, str)
                default = json.loads(field['defaultValueFormula'])
            elif field['defaultValueFormula'].lower() in ('true', 'false'):
                # bool not important - probably not used
                default = field['defaultValueFormula'].lower() == 'true'
            else:
                default = None
                params['ref_comment'] = 'Warning: not a simple defaultValueFormula'
        else:
            default = None
        if default is not None:
            params['default'] = default
        elif field['defaultedOnCreate'] and field['createable'] and DJANGO_50_PLUS:
            params['db_default'] = SymbolicModelsName('DEFAULTED_ON_CREATE')
            params['blank'] = True
        elif field['calculatedFormula']:
            params['sf_formula'] = field['calculatedFormula']

        if field['inlineHelpText']:
            params['help_text'] = field['inlineHelpText']
        if field['picklistValues']:
            params['choices'] = [(x['value'], x['label']) for x in field['picklistValues'] if x['active']]
            max_inspectdb_picklist_picklist_length = getattr(settings, 'SF_MAX_INSPECTDB_PICKLIST_LENGTH', 4000)
            if len(repr(params['choices'])) < max_inspectdb_picklist_picklist_length:
                params['max_len'] = max(len(x['value']) for x in field['picklistValues'] if x['active'])
            else:
                params['ref_comment'] = 'Too long choices skipped'
                del params['choices']
        if field['type'] == 'reference' and not self.references_to(field):
            if not field['referenceTo']:
                params['ref_comment'] = 'No Reference to a table'
            else:
                params['ref_comment'] = 'References to missing tables: {}'.format(self.references_to(field, all=True))
        return params

    def references_to(self, field: Dict[str, Any], all: bool = False) -> Optional[List[str]]:  # pylint:disable=redefined-builtin # noqa
        if field['type'] != 'reference':
            return None
        reference_to_valid = [x for x in field['referenceTo'] if x in self._table_names]
        reference_to_invalid = ['-{}'.format(x) for x in field['referenceTo'] if x not in self._table_names]
        return reference_to_valid + reference_to_invalid if all else reference_to_valid

    # -- standard methods

    def get_table_description(self, cursor: _Cursor, table_name: str) -> List[FieldInfo]:
        "Returns a description of the table, with the DB-API cursor.description interface."
        # pylint:disable=too-many-locals,unused-argument
        result = []
        for field in self.table_description_cache(table_name)['fields']:
            params = self.get_field_params(field)
            if field['type'] == 'reference' and not self.references_to(field):
                field['type'] = 'string'
            if field['calculatedFormula']:
                # calculated formula field are without length in Salesforce 45 Spring '19,
                # but Django requires a length, though the field is read only and never written
                field['length'] = 1300
            if 'max_len' in params:
                if params['max_len'] > field['length']:
                    field['length'] = params['max_len']
                del params['max_len']
            optional_kw = {'collation': None} if DJANGO_32_PLUS else {}
            # We prefer "length" over "byteLength" for "internal_size".
            # (because strings have usually: byteLength == 3 * length)
            if field['type'] == 'double' and field['precision'] == -1 and field['scale'] == -1:
                # started important in tooling API 60.0 Spring '24 - e.g. tooling.IdeasSettings.half_life
                field['type'] = 'float'
            result.append(FieldInfo(  # type: ignore[call-arg] # problem with a conditional type
                field['name'],       # name,
                field['type'],       # type_code,
                field['length'],     # display_size,
                field['length'],     # internal_size,
                field['precision'],  # precision,
                field['scale'],      # scale,
                field['nillable'],   # null_ok,
                params.get('default'),  # default
                # 'collation' paramater is used only in Django >= 3.2. It is before 'params', but we pass it by **kw
                params=params,
                **optional_kw
            ))
        return result

    # unused because feature 'supports_table_check_constraints == False'
    def get_sequences(self, cursor: _Cursor, table_name: str, table_fields=()  # pragma: no cover
                      ) -> List[Dict[str, str]]:
        pk_col = self.get_primary_key_column(cursor, table_name) or 'Id'
        return [{'table': table_name, 'column': pk_col}]

    def get_relations(self, cursor: _Cursor, table_name: str) -> Dict[str, Tuple[str, 'SfProtectName']]:
        """
        Returns a dictionary of {field_index: (field_index_other_table, other_table)}
        representing all relationships to the given table. Indexes are 0-based.
        """
        # pylint:disable=global-statement,too-many-locals,too-many-nested-blocks,unused-argument
        def table2model(table_name: str) -> str:
            return SfProtectName(table_name).title().replace(' ', '').replace('-', '')
        global last_introspection
        result = {}
        reverse = {}  # type: Dict[str, List[str]]
        important_related_names = []
        fields_map = {}  # type: Dict[str, Dict[str, Any]]
        for _, field in enumerate(self.table_description_cache(table_name)['fields']):
            references_to = self.references_to(field)
            if references_to:
                params = OrderedDict()
                relationship_order = field['relationshipOrder']
                reference_to_name = SfProtectName(references_to[0])
                if relationship_order is None:
                    relationship_tmp = set()
                    for rel in references_to:
                        for chld in self.table_description_cache(rel)['childRelationships']:
                            if chld['childSObject'] == table_name and chld['field'] == field['name']:
                                relationship_tmp.add(chld['cascadeDelete'])
                    assert len(relationship_tmp) <= 1
                    if True in relationship_tmp:
                        relationship_order = '*'
                params['refs'] = (self.references_to(field, all=True), relationship_order)
                result[field['name']] = ('Id', reference_to_name)
                reverse.setdefault(reference_to_name, []).append(field['name'])
                params.update(self.get_field_params(field))
                fields_map[field['name']] = params
        for ref, ilist in reverse.items():
            # Example of back_collision: a class Aaa has a ForeignKey to a class
            # Bbb and the class Bbb has any field with the name 'aaa'.
            back_name_collisions = [
                x['name'] for x in self.table_description_cache(ref)['fields']
                if re.sub('Id$' if x['type'] == 'reference' else '', '',
                          re.sub('__c$', '', x['name'])
                          ).replace('_', '').lower() == table2model(table_name).lower()]
            # add `related_name` only if necessary
            if len(ilist) > 1 or back_name_collisions:
                important_related_names.extend(ilist)
        last_introspection = LastIntrospection(
            model_name=table2model(table_name),
            important_related_names=important_related_names,
            fields_map=fields_map,
        )
        return result

    # never used until real migrations will be supported
    def get_key_columns(self, cursor: _Cursor, table_name: str) -> List[Tuple[str, str, str]]:  # pragma: no cover
        """
            (column_name, referenced_table_name, referenced_column_name)
        """
        key_columns = []
        for name, item in self.get_constraints(cursor, table_name).items():
            if not item['primary_key']:
                key_columns.append((name,) + item['foreign_key'])
        return key_columns

    def get_constraints(self, cursor: _Cursor, table_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves any constraints or keys (unique, pk, fk, check, index)
        across one or more columns.

        Returns a dict mapping constraint names to their attributes,
        where attributes is a dict with keys:
         * columns: List of columns this covers
         * primary_key: True if primary key, False otherwise
         * unique: True if this is a unique constraint, False otherwise
         * foreign_key: (table, column) of target, or None
         * check: True if check constraint, False otherwise
         * index: True if index, False otherwise.                            # unused
         * orders: The order (ASC/DESC) defined for the columns of indexes   # unused
         * type: The type of the index (btree, hash, etc.)                   # unused
        """
        result = {}
        for field in self.table_description_cache(table_name)['fields']:
            if field['type'] in ('id', 'reference') or field['unique']:
                result[field['name']] = dict(
                    columns=[field['name']],
                    primary_key=(field['type'] == 'id'),
                    unique=field['unique'],
                    foreign_key=(field['referenceTo'], 'id'),
                    check=False,
                )
        return result

    # -- custom methods

    def get_additional_meta(self, table_name: str) -> List[str]:
        item = [x for x in self.table_list_cache['sobjects'] if x['name'] == table_name][0]
        return ["verbose_name = %r" % item['label'],
                "verbose_name_plural = %r" % item['labelPlural'],
                "# keyPrefix = %r" % item['keyPrefix'],
                ]

    @property
    def converted_lead_status(self) -> str:
        if self._converted_lead_status is None:
            cur = self.connection.cursor()
            cur.execute("SELECT MasterLabel FROM LeadStatus "
                        "WHERE IsConverted = True ORDER BY SortOrder LIMIT 1")
            self._converted_lead_status = cur.fetchone()[0]
        return self._converted_lead_status


class SymbolicModelsName:
    """A symbolic name from the `models` module.
    >>> from salesforce import models
    >>> assert models.READ_ONLY == 3
    >>> SymbolicModelsName('READ_ONLY').value
    3
    >>> [SymbolicModelsName('READ_ONLY')]
    [models.READ_ONLY]
    """
    def __init__(self, name: str, arg: Any = None) -> None:
        self.name = 'models.%s' % name
        # it is imported from salesforce.fields due to dependencies,
        # but it is the same as in salesforce.models
        self.value = getattr(salesforce.fields, name)
        if arg is not None:
            self.name = '{}({})'.format(self.name, repr(arg))
            self.value = self.value(arg)

    def __repr__(self) -> str:
        return self.name


class SfProtectName(str):
    """
    Protect CamelCase class names and improve NOT_camelCase names by injecting
    a milder method ".title()" on the table name string into Django method
    inspectdb.
    >>> SfProtectName('AccountContactRole').title()
    'AccountContactRole'
    >>> SfProtectName('some_STRANGE2TableName__c').title()
    'SomeStrange2TableName'
    >>> assert SfProtectName('an_ODD2TableName__c') == 'an_ODD2TableName__c'
    """
    type = 't'  # 't'=table, 'v'=view

    # This better preserves the names. It is exact for all SF builtin tables,
    # though not perfect for names with more consecutive upper case characters,
    # e.g 'MyURLTable__c' -> 'MyUrltable' is still better than 'MyurltableC'.
    def title(self) -> str:
        name = re.sub(r'__c$', '', self)   # fixed custom name
        return re.sub(r'([a-z0-9])(?=[A-Z])', r'\1_', name).title().replace('_', '')


reverse_models_names = dict((obj.value, obj) for obj in
                            [SymbolicModelsName(name) for name in
                             ('NOT_UPDATEABLE', 'NOT_CREATEABLE', 'READ_ONLY')
                             ])
