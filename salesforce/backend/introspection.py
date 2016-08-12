# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce introspection code.
"""

import logging
import re

from salesforce import DJANGO_18_PLUS
from salesforce.backend import driver
from salesforce.fields import SF_PK
import salesforce.fields

from django.conf import settings
if DJANGO_18_PLUS:
    from django.db.backends.base.introspection import BaseDatabaseIntrospection
else:
    from django.db.backends import BaseDatabaseIntrospection

from salesforce.backend import compiler, query

# require "simplejson" to ensure that it is available to "requests" hook.
import simplejson

from collections import OrderedDict
from django.utils.text import camel_case_to_spaces

log = logging.getLogger(__name__)


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
        'base64'                        : 'TextField',
        'boolean'                       : 'BooleanField',
        'byte'                          : 'SmallIntegerField',
        'date'                          : 'DateField',
        'datetime'                      : 'DateTimeField',
        'double'                        : 'DecimalField',
        'int'                           : 'IntegerField',
        'string'                        : 'CharField',
        'time'                          : 'TimeField',
        'anyType'                       : 'CharField',
        'calculated'                    : 'CharField',
        'combobox'                      : 'CharField',
        'currency'                      : 'DecimalField',
        'datacategorygroupreference'    : 'CharField',
        'email'                         : 'EmailField',
        'encryptedstring'               : 'CharField',
        'id'                            : 'AutoField',
        'masterrecord'                  : 'CharField',
        # multipicklist can be implemented by a descendant with a special validator + widget
        'multipicklist'                 : 'CharField',
        'percent'                       : 'DecimalField',
        'phone'                         : 'CharField',
        # picklist is ('CharField', {'choices': (...)})
        'picklist'                      : 'CharField',
        'reference'                     : 'ForeignKey',
        'textarea'                      : 'TextField',
        'url'                           : 'URLField',
    }

    def __init__(self, conn):
        BaseDatabaseIntrospection.__init__(self, conn)
        self._table_list_cache = None
        self._table_description_cache = {}
        self._converted_lead_status = None

    @property
    def table_list_cache(self):
        if self._table_list_cache is None:
            url = query.rest_api_url(self.connection.sf_session, 'sobjects')
            log.debug('Request API URL: %s' % url)
            response = driver.handle_api_exceptions(url, self.connection.sf_session.get)
            # charset is detected from headers by requests package
            self._table_list_cache = response.json(object_pairs_hook=OrderedDict)
        return self._table_list_cache

    def table_description_cache(self, table):
        if table not in self._table_description_cache:
            url = query.rest_api_url(self.connection.sf_session, 'sobjects', table, 'describe/')
            log.debug('Request API URL: %s' % url)
            response = driver.handle_api_exceptions(url, self.connection.sf_session.get)
            self._table_description_cache[table] = response.json(object_pairs_hook=OrderedDict)
            assert self._table_description_cache[table]['fields'][0]['type'] == 'id'
            assert self._table_description_cache[table]['fields'][0]['name'] == 'Id'
            del self._table_description_cache[table]['fields'][0]
        return self._table_description_cache[table]

    def table_name_converter(self, name):
        return name if (name.lower() != 'id' or DJANGO_18_PLUS) else SF_PK

    def get_table_list(self, cursor):
        "Returns a list of table names in the current database."
        result = [SfProtectName(x['name'])
                for x in self.table_list_cache['sobjects']]
        return result

    def get_table_description(self, cursor, table_name):
        "Returns a description of the table, with the DB-API cursor.description interface."
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
            if field['defaultValue'] is not None:
                params['default'] = field['defaultValue']
            if field['inlineHelpText']:
                params['help_text'] = field['inlineHelpText']
            if field['picklistValues']:
                params['choices'] = [(x['value'], x['label']) for x in field['picklistValues'] if x['active']]
            if field['defaultedOnCreate'] and field['createable']:
                params['default'] = SymbolicModelsName('DEFAULTED_ON_CREATE')
            if field['type'] == 'reference' and not field['referenceTo']:
                params['ref_comment'] = 'No Reference table'
                field['type'] = 'string'
            # We prefer "length" over "byteLength" for "internal_size".
            # (because strings have usually: byteLength == 3 * length)
            result.append((
                field['name'], # name,
                field['type'], # type_code,
                field['length'], # display_size,
                field['length'], # internal_size,
                field['precision'], # precision,
                field['scale'], # scale,
                field['nillable'], # null_ok,
                params,
            ))
        return result

    def get_relations(self, cursor, table_name):
        """
        Returns a dictionary of {field_index: (field_index_other_table, other_table)}
        representing all relationships to the given table. Indexes are 0-based.
        """
        global last_introspected_model, last_with_important_related_name, last_read_only, last_refs
        table2model = lambda table_name: (SfProtectName(table_name).title()
                .replace(' ', '').replace('-', ''))
        result = {}
        reverse = {}
        last_with_important_related_name = []
        last_read_only = {}
        last_refs = {}
        for i, field in enumerate(self.table_description_cache(table_name)['fields']):
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
                if DJANGO_18_PLUS:
                    result[field['name']] = ('Id', reference_to_name)
                else:
                    INDEX_OF_PRIMARY_KEY = 0
                    result[i] = (INDEX_OF_PRIMARY_KEY, reference_to_name)
                reverse.setdefault(reference_to_name, []).append(field['name'])
                if not field['updateable'] or not field['createable']:
                    sf_read_only = (0 if field['updateable'] else 1) | (0 if field['createable'] else 2)
                    # use symbolic names NOT_UPDATEABLE, NON_CREATABLE, READ_ONLY instead of 1, 2, 3
                    last_read_only[field['name']] = reverse_models_names[sf_read_only]
        for ref, ilist in reverse.items():
            # Example of back_collision: a class Aaa has a ForeignKey to a class
            # Bbb and the class Bbb has any field with the name 'aaa'.
            back_name_collisions = [x['name'] for x
                    in self.table_description_cache(ref)['fields']
                    if re.sub('Id$' if x['type'] == 'reference' else '', '',
                        re.sub('__c$', '', x['name'])).replace('_', '').lower()
                    == table2model(table_name).lower()]
            # add `related_name` only if necessary
            if len(ilist) > 1 or back_name_collisions:
                last_with_important_related_name.extend(ilist)
        last_introspected_model = table2model(table_name)
        return result

    def get_indexes(self, cursor, table_name):
        """
        Returns a dictionary of fieldname -> infodict for the given table,
        where each infodict is in the format:
            {'primary_key': boolean representing whether it's the primary key,
             'unique': boolean representing whether it's a unique index}
        """
        result = {}
        for field in self.table_description_cache(table_name)['fields']:
            if field['type'] == 'id' or field['unique']:
                result[field['name']] = dict(
                        primary_key=(field['type'] == 'id'),
                        unique=field['unique']
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
            self._converted_lead_status = cur.fetchone()['MasterLabel']
        return self._converted_lead_status


class SymbolicModelsName(object):
    """A symbolic name from the `models` module.
    >>> assert models.READ_ONLY == 3
    >>> SymbolicName('READ_ONLY').value
    3
    >>> [SymbolicName('READ_ONLY')]
    [models.READ_ONLY]
    """
    def __init__(self, name):
        self.name = 'models.%s' % name
        # it is imported from salesforce.fields due to dependencies,
        # but it is the same as in salesforce.models
        self.value = getattr(salesforce.fields, name)

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
    [SymbolicModelsName(name) for name in ('NOT_UPDATEABLE', 'NOT_CREATEABLE', 'READ_ONLY')]
)
