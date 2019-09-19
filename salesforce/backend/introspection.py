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

from django.db.backends.base.introspection import (
    BaseDatabaseIntrospection, FieldInfo as BaseFieldInfo, TableInfo,
)
from django.utils.text import camel_case_to_spaces
# require "simplejson" to ensure that it is available to "requests" hook.
import simplejson  # NOQA pylint:disable=unused-import

import salesforce.fields
from salesforce.backend import DJANGO_111_PLUS

log = logging.getLogger(__name__)

field_info_fields = BaseFieldInfo._fields + (() if DJANGO_111_PLUS else ('default',)) + ('params',)
FieldInfo = namedtuple('FieldInfo', field_info_fields)  # pylint:disable=invalid-name

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
    'DatasetExportEvent', 'VisibilityUpdateEvent',  # new in API 46.0 Summer '19 - missing 'Id'
    'FlowExecutionErrorEvent',  # new in API 47.0 Winter '20 - missing 'Id'
]

# these global variables are for `salesforce.management.commands.inspectdb`
last_introspected_model = None
last_with_important_related_name = None  # pylint:disable=invalid-name
last_read_only = None
last_refs = None


class DatabaseIntrospection(BaseDatabaseIntrospection):
    """
    The most comfortable and complete output is by:
        table_list_cache:               property with database and tables attributes
        table_description_cache(name):  method   with table and fields attributes
    Everything is with caching the results for the next use.
    Other methods are very customized with hooks for
    by django.core.management.commands.inspectdb
    """
    # pylint:disable=abstract-method  # undefined: get_key_columns, get_sequences

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
    }

    def __init__(self, conn):
        BaseDatabaseIntrospection.__init__(self, conn)
        self._table_list_cache = None
        self._table_description_cache = {}
        self._converted_lead_status = None

    @property
    def table_list_cache(self):
        if self._table_list_cache is None:
            log.debug('Request API URL: GET sobjects')
            response = self.connection.connection.handle_api_exceptions('GET', 'sobjects/')
            # charset is detected from headers by requests package
            self._table_list_cache = response.json(object_pairs_hook=OrderedDict)
            self._table_list_cache['sobjects'] = [
                x for x in self._table_list_cache['sobjects']
                if x['name'] not in PROBLEMATIC_OBJECTS and not x['name'].endswith('ChangeEvent')
            ]
        return self._table_list_cache

    def table_description_cache(self, table):
        if table not in self._table_description_cache:
            log.debug('Request API URL: GET sobjects/%s/describe', table)
            response = self.connection.connection.handle_api_exceptions('GET', 'sobjects', table, 'describe/')
            self._table_description_cache[table] = response.json(object_pairs_hook=OrderedDict)
            assert self._table_description_cache[table]['fields'][0]['type'] == 'id', (
                "Invalid type of the first field in the table '{}'".format(table))
            assert self._table_description_cache[table]['fields'][0]['name'] == 'Id', (
                "Invalid name of the first field in the table '{}'".format(table))
            del self._table_description_cache[table]['fields'][0]
        return self._table_description_cache[table]

    def get_table_list(self, cursor):
        "Returns a list of table names in the current database."
        result = [TableInfo(SfProtectName(x['name']), 't') for x in self.table_list_cache['sobjects']]
        return result

    def get_table_description(self, cursor, table_name):
        "Returns a description of the table, with the DB-API cursor.description interface."
        # pylint:disable=too-many-locals,unused-argument
        result = []
        for field in self.table_description_cache(table_name)['fields']:
            params = OrderedDict()
            if field['label'] and field['label'] != camel_case_to_spaces(re.sub('__c$', '', field['name'])).title():
                params['verbose_name'] = field['label']
            if not field['updateable'] or not field['createable']:
                # Fields that are result of a formula or system fields modified
                # by triggers or by other apex code
                sf_read_only = (0 if field['updateable'] else 1) | (0 if field['createable'] else 2)
                # use symbolic names NOT_UPDATEABLE, NON_CREATABLE, READ_ONLY instead of 1, 2, 3
                params['sf_read_only'] = reverse_models_names[sf_read_only]
            if field['defaultedOnCreate']:
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
            if field['type'] == 'reference' and not field['referenceTo']:
                params['ref_comment'] = 'No Reference table'
                field['type'] = 'string'
            if field['calculatedFormula']:
                # calculated formula field are without length in Salesforce 45 Spring '19,
                # but Django requires a length, though the field is read only and never written
                field['length'] = 1300
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

    def get_relations(self, cursor, table_name):
        """
        Returns a dictionary of {field_index: (field_index_other_table, other_table)}
        representing all relationships to the given table. Indexes are 0-based.
        """
        # pylint:disable=global-statement,too-many-locals,too-many-nested-blocks,unused-argument
        def table2model(table_name):
            return SfProtectName(table_name).title().replace(' ', '').replace('-', '')
        global last_introspected_model, last_read_only, last_refs
        global last_with_important_related_name  # pylint:disable=invalid-name
        result = {}
        reverse = {}
        last_with_important_related_name = []
        last_read_only = {}
        last_refs = {}
        for _, field in enumerate(self.table_description_cache(table_name)['fields']):
            if field['type'] == 'reference' and field['referenceTo']:
                reference_to_name = SfProtectName(field['referenceTo'][0])
                relationship_order = field['relationshipOrder']
                if relationship_order is None:
                    relationship_tmp = set()
                    for rel in field['referenceTo']:
                        for chld in self.table_description_cache(rel)['childRelationships']:
                            if chld['childSObject'] == table_name and chld['field'] == field['name']:
                                relationship_tmp.add(chld['cascadeDelete'])
                    assert len(relationship_tmp) <= 1
                    if True in relationship_tmp:
                        relationship_order = '*'
                last_refs[field['name']] = (field['referenceTo'], relationship_order)
                result[field['name']] = ('Id', reference_to_name)
                reverse.setdefault(reference_to_name, []).append(field['name'])
                if not field['updateable'] or not field['createable']:
                    sf_read_only = (0 if field['updateable'] else 1) | (0 if field['createable'] else 2)
                    # use symbolic names NOT_UPDATEABLE, NON_CREATABLE, READ_ONLY instead of 1, 2, 3
                    last_read_only[field['name']] = reverse_models_names[sf_read_only]
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
                last_with_important_related_name.extend(ilist)
        last_introspected_model = table2model(table_name)
        return result

    def get_constraints(self, cursor, table_name):
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
         * index: True if index, False otherwise.
         * orders: The order (ASC/DESC) defined for the columns of indexes
         * type: The type of the index (btree, hash, etc.)
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

    def get_additional_meta(self, table_name):
        item = [x for x in self.table_list_cache['sobjects'] if x['name'] == table_name][0]
        return ["verbose_name = '%s'" % item['label'],
                "verbose_name_plural = '%s'" % item['labelPlural'],
                "# keyPrefix = '%s'" % item['keyPrefix'],
                ]

    @property
    def converted_lead_status(self):
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
    def __init__(self, name, arg=None):
        self.name = 'models.%s' % name
        # it is imported from salesforce.fields due to dependencies,
        # but it is the same as in salesforce.models
        self.value = getattr(salesforce.fields, name)
        if arg is not None:
            self.name = '{}({})'.format(self.name, repr(arg))
            self.value = self.value(arg)

    def __repr__(self):
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
    def title(self):
        name = re.sub(r'__c$', '', self)   # fixed custom name
        return re.sub(r'([a-z0-9])(?=[A-Z])', r'\1_', name).title().replace('_', '')

    @property
    def name(self):
        return self


reverse_models_names = dict((obj.value, obj) for obj in
                            [SymbolicModelsName(name) for name in
                             ('NOT_UPDATEABLE', 'NOT_CREATEABLE', 'READ_ONLY')
                             ])
