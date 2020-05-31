# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce introspection code.  (like django.db.backends.*.introspection)
"""

import logging
import re
from collections import OrderedDict, namedtuple
from typing import Any, Dict, List, Optional, Set, Tuple

from django.db.backends.base.introspection import (
    BaseDatabaseIntrospection, FieldInfo as BaseFieldInfo, TableInfo,
)
from django.utils.text import camel_case_to_spaces
from django.db.backends.utils import CursorWrapper as _Cursor  # for typing
# require "simplejson" to ensure that it is available to "requests" hook.
import simplejson  # NOQA pylint:disable=unused-import

import salesforce.fields

log = logging.getLogger(__name__)

FieldInfo = namedtuple(
    'FieldInfo',
    'name type_code display_size internal_size precision scale null_ok default'
    ' params'  # the last name 'params' is our extension for Salesforce
)  # pylint:disable=invalid-name
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
        self._table_names = set()  # type: Set[str]
        self._table_list_cache = None  # type: Optional[Dict[str, Any]]
        self._table_description_cache = {}  # type: Dict[str, Dict[str, Any]]
        self._converted_lead_status = None  # type: Optional[str]
        self.is_tooling_api = False  # modified by other modules

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
            log.debug('Request API URL: GET sobjects/%s/describe', table)
            response = self.connection.connection.handle_api_exceptions('GET', self.sobjects_prefix, table, 'describe/'
                                                                        )
            self._table_description_cache[table] = response.json(object_pairs_hook=OrderedDict)
            field_list = self._table_description_cache[table]['fields']
            # 'Id' field is sometimes not the first field in tooling metadata SObjects
            id_field, = [x for x in field_list if x['name'] == 'Id']
            assert id_field['type'] == 'id', (
                "Invalid type of the field 'Id' in table '{}'".format(table))
            del field_list[field_list.index(id_field)]
        return self._table_description_cache[table]

    def get_table_list(self, cursor: _Cursor) -> List[TableInfo]:
        "Returns a list of table names in the current database."
        result = [TableInfo(SfProtectName(x['name']), 't') for x in self.table_list_cache['sobjects']]
        return result

    def get_field_params(self, field: Dict[str, Any]) -> Dict[str, Any]:
        params = OrderedDict()
        if field['label'] and field['label'] != camel_case_to_spaces(re.sub('__c$', '', field['name'])).title():
            params['verbose_name'] = field['label']
        if not field['updateable'] or not field['createable']:
            # Fields that are result of a formula or system fields modified
            # by triggers or by other apex code
            # use symbolic names NOT_UPDATEABLE, NOT_CREATABLE, READ_ONLY instead of 1, 2, 3
            sf_read_only = (0 if field['updateable'] else 1) | (0 if field['createable'] else 2)
            params['sf_read_only'] = reverse_models_names[sf_read_only]
        if field['defaultedOnCreate'] and field['createable']:
            if field['defaultValue'] is None:
                params['default'] = SymbolicModelsName('DEFAULTED_ON_CREATE')
            else:
                params['default'] = SymbolicModelsName('DefaultedOnCreate', field['defaultValue'])
        elif field['defaultValue'] is not None:
            params['default'] = field['defaultValue']
        if field['inlineHelpText']:
            params['help_text'] = field['inlineHelpText']
        if field['picklistValues']:
            params['choices'] = [(x['value'], x['label']) for x in field['picklistValues'] if x['active']]
            params['max_len'] = max(len(x['value']) for x in field['picklistValues'] if x['active'])
        if field['type'] == 'reference' and not self.references_to(field):
            if not field['referenceTo']:
                params['ref_comment'] = 'No Reference table'
            else:
                params['ref_comment'] = 'Invalid References: {}'.format(self.references_to(field, all=True))
        return params

    def references_to(self, field: Dict[str, Any], all: bool = False) -> Optional[List[str]]:
        if field['type'] != 'reference':
            return None
        reference_to_valid = [x for x in field['referenceTo'] if x in self._table_names]
        reference_to_invalid = ['-{}'.format(x) for x in field['referenceTo'] if x not in self._table_names]
        return reference_to_valid + reference_to_invalid if all else reference_to_valid

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
            # We prefer "length" over "byteLength" for "internal_size".
            # (because strings have usually: byteLength == 3 * length)
            result.append(FieldInfo(
                field['name'],       # name,
                field['type'],       # type_code,
                field['length'],     # display_size,
                field['length'],     # internal_size,
                field['precision'],  # precision,
                field['scale'],      # scale,
                field['nillable'],   # null_ok,
                params.get('default'),  # default
                params,
            ))
        return result

    def get_sequences(self, cursor: _Cursor, table_name: str, table_fields=()) -> List[Dict[str, str]]:
        pk_col = self.get_primary_key_column(cursor, table_name) or 'Id'
        return [{'table': table_name, 'column': pk_col}]

    # never used until real migrations will be supported
    def get_key_columns(self, cursor: _Cursor, table_name: str) -> List[Tuple[str, str, str]]:
        """
            (column_name, referenced_table_name, referenced_column_name)
        """
        key_columns = []
        for name, item in self.get_constraints(cursor, table_name).items():
            if not item['primary_key']:
                key_columns.append((name,) + item['foreign_key'])
        return key_columns

    def get_relations(self, cursor: _Cursor, table_name: str) -> Dict[str, Tuple[str, 'SfProtectName']]:
        """
        Returns a dictionary of {field_index: (field_index_other_table, other_table)}
        representing all relationships to the given table. Indexes are 0-based.
        """
        # pylint:disable=global-statement,too-many-locals,too-many-nested-blocks,unused-argument
        def table2model(table_name):
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

# pylint:disable=too-few-public-methods


class SymbolicModelsName(object):
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

    @property
    def name(self) -> 'SfProtectName':
        return self


reverse_models_names = dict((obj.value, obj) for obj in
                            [SymbolicModelsName(name) for name in
                             ('NOT_UPDATEABLE', 'NOT_CREATEABLE', 'READ_ONLY')
                             ])
