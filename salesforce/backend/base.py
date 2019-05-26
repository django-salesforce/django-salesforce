# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce database backend for Django.  (like django,db.backends.*.base)
"""

from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from django.db.backends.base.base import BaseDatabaseWrapper

from salesforce.backend import DJANGO_111_PLUS
from salesforce.backend.client import DatabaseClient
from salesforce.backend.creation import DatabaseCreation
from salesforce.backend.features import DatabaseFeatures
from salesforce.backend.validation import DatabaseValidation
from salesforce.backend.operations import DatabaseOperations
from salesforce.backend.introspection import DatabaseIntrospection
from salesforce.backend.schema import DatabaseSchemaEditor
# from django.db.backends.signals import connection_created
from salesforce.backend.utils import CursorWrapper
from salesforce.dbapi import driver as Database
from salesforce.dbapi.driver import IntegrityError, DatabaseError, SalesforceError  # NOQA pylint:disable=unused-import

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

__all__ = ('DatabaseWrapper', 'DatabaseError', 'SalesforceError',)


class DatabaseWrapper(BaseDatabaseWrapper):
    """
    Core class that provides all DB support.
    """
    # pylint:disable=abstract-method,too-many-instance-attributes
    #     undefined abstract methods: _start_transaction_under_autocommit, create_cursor, is_usable

    vendor = 'salesforce'
    display_name = 'Salesforce'

    # Operators [contains, startswithm, endswith] are incorrectly
    # case insensitive like sqlite3.
    operators = {
        'exact': '= %s',
        'iexact': 'LIKE %s',
        'contains': 'LIKE %s',
        'icontains': 'LIKE %s',
        # 'regex': 'REGEXP %s',  # unsupported
        # 'iregex': 'REGEXP %s',
        'gt': '> %s',
        'gte': '>= %s',
        'lt': '< %s',
        'lte': '<= %s',
        'startswith': 'LIKE %s',
        'endswith': 'LIKE %s',
        'istartswith': 'LIKE %s',
        'iendswith': 'LIKE %s',
    }

    Database = Database
    SchemaEditorClass = DatabaseSchemaEditor

    if DJANGO_111_PLUS:
        # Classes instantiated in __init__().
        client_class = DatabaseClient
        creation_class = DatabaseCreation
        features_class = DatabaseFeatures
        introspection_class = DatabaseIntrospection
        ops_class = DatabaseOperations
        validation_class = DatabaseValidation

    def __init__(self, settings_dict, alias=None):
        if alias is None:
            alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
        super(DatabaseWrapper, self).__init__(settings_dict, alias)

        self.validate_settings(settings_dict)

        if not DJANGO_111_PLUS:
            self.features = DatabaseFeatures(self)
            self.ops = DatabaseOperations(self)
            self.client = DatabaseClient(self)
            self.creation = DatabaseCreation(self)
            self.introspection = DatabaseIntrospection(self)
            self.validation = DatabaseValidation(self)
        self._is_sandbox = None

    @property
    def sf_session(self):
        if self.connection is None:
            self.connect()
        return self.connection.sf_session

    def get_connection_params(self):
        settings_dict = self.settings_dict
        params = settings_dict.copy()
        params.update(settings_dict['OPTIONS'])
        return params

    def get_new_connection(self, conn_params):
        # only simulated a connection interface without connecting really
        return Database.connect(settings_dict=conn_params, alias=self.alias)

    def init_connection_state(self):
        pass  # nothing to init

    def _set_autocommit(self, autocommit):
        # SF REST API uses autocommit, but until rollback it is not a
        # serious problem to ignore autocommit off
        pass

    def validate_settings(self, settings_dict):
        # pylint:disable=
        for k in ('ENGINE', 'CONSUMER_KEY', 'CONSUMER_SECRET', 'USER', 'PASSWORD', 'HOST'):
            if k not in settings_dict:
                raise ImproperlyConfigured("Required '%s' key missing from '%s' database settings." % (k, self.alias))
            if not settings_dict[k]:
                raise ImproperlyConfigured("'%s' key is the empty string in '%s' database settings." % (k, self.alias))

        try:
            urlparse(settings_dict['HOST'])
        except Exception as exc:
            raise ImproperlyConfigured("'HOST' key in '%s' database settings should be a valid URL: %s" %
                                       (self.alias, exc))

    def cursor(self):
        """
        Return a fake cursor for accessing the Salesforce API with SOQL.
        """
        return CursorWrapper(self)

    def quote_name(self, name):
        """
        Do not quote column and table names in the SOQL dialect.
        """
        # pylint:disable=no-self-use
        return name

    @property
    def is_sandbox(self):
        if self._is_sandbox is None:
            cur = self.cursor()
            cur.execute("SELECT IsSandbox FROM Organization")
            self._is_sandbox = cur.fetchone()[0]
        return self._is_sandbox
