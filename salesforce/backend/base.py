# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce database backend for Django.
"""

import logging
import requests
import sys
import threading

from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from requests.adapters import HTTPAdapter

from salesforce.auth import SalesforcePasswordAuth
from salesforce.backend.client import DatabaseClient
from salesforce.backend.creation import DatabaseCreation
from salesforce.backend.validation import DatabaseValidation
from salesforce.backend.operations import DatabaseOperations
from salesforce.backend.driver import IntegrityError, DatabaseError, SalesforceError  # NOQA - TODO
from salesforce.backend import introspection, driver as Database, get_max_retries
# from django.db.backends.signals import connection_created

from salesforce import DJANGO_18_PLUS
if DJANGO_18_PLUS:
    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.backends.base.features import BaseDatabaseFeatures
else:
    from django.db.backends import BaseDatabaseWrapper, BaseDatabaseFeatures
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

__all__ = ('DatabaseWrapper', 'DatabaseError', 'SalesforceError',)
log = logging.getLogger(__name__)

connect_lock = threading.Lock()


class DatabaseFeatures(BaseDatabaseFeatures):
    """
    Features this database provides.
    """
    allows_group_by_pk = True
    supports_unspecified_pk = False
    can_return_id_from_insert = False
    has_bulk_insert = True
    # TODO If the following would be True, it requires a good relation name resolution
    supports_select_related = False
    # Though Salesforce doesn't support transactions, the setting
    # `supports_transactions` is used only for switching between rollback or
    # cleaning the database in testrunner after every test and loading fixtures
    # before it, however SF does not support any of these and all test data must
    # be loaded and cleaned by the testcase code. From the viewpoint of SF it is
    # irrelevant, but due to issue #28 (slow unit tests) it should be True.
    supports_transactions = True

    # Never use `interprets_empty_strings_as_nulls=True`. It is an opposite
    # setting for Oracle, while Salesforce saves nulls as empty strings not vice
    # versa.


class DatabaseWrapper(BaseDatabaseWrapper):
    """
    Core class that provides all DB support.
    """
    vendor = 'salesforce'
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

    def __init__(self, settings_dict, alias=None):
        if alias is None:
            alias = getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce')
        super(DatabaseWrapper, self).__init__(settings_dict, alias)

        self.validate_settings(settings_dict)

        self.features = DatabaseFeatures(self)
        self.ops = DatabaseOperations(self)
        self.client = DatabaseClient(self)
        self.creation = DatabaseCreation(self)
        self.introspection = introspection.DatabaseIntrospection(self)
        self.validation = DatabaseValidation(self)
        self._sf_session = None
        self._is_sandbox = None
        # The SFDC database is connected as late as possible if only tests
        # are running. Some tests don't require a connection.
        if not getattr(settings, 'SF_LAZY_CONNECT', 'test' in sys.argv):
            self.make_session()

    def make_session(self):
        """Authenticate and get the name of assigned SFDC data server"""
        with connect_lock:
            if self._sf_session is None:
                sf_session = requests.Session()
                # TODO configurable class Salesforce***Auth
                sf_session.auth = SalesforcePasswordAuth(db_alias=self.alias,
                                                         settings_dict=self.settings_dict)
                sf_instance_url = sf_session.auth.instance_url
                sf_requests_adapter = HTTPAdapter(max_retries=get_max_retries())
                sf_session.mount(sf_instance_url, sf_requests_adapter)
                # Additional header works, but the improvement is immeasurable for
                # me. (less than SF speed fluctuation)
                # sf_session.header = {'accept-encoding': 'gzip, deflate', 'connection': 'keep-alive'}
                self._sf_session = sf_session

    @property
    def sf_session(self):
        if self._sf_session is None:
            self.make_session()
        return self._sf_session

    def get_connection_params(self):
        settings_dict = self.settings_dict
        params = settings_dict.copy()
        params.update(settings_dict['OPTIONS'])
        return params

    def get_new_connection(self, conn_params):
        # only simulated a connection interface without connecting really
        return Database.connect(**conn_params)

    def init_connection_state(self):
        pass  # nothing to init

    def _set_autocommit(self, autocommit):
        # SF REST API uses autocommit, but until rollback it is not a
        # serious problem to ignore autocommit off
        pass

    def validate_settings(self, d):
        for k in ('ENGINE', 'CONSUMER_KEY', 'CONSUMER_SECRET', 'USER', 'PASSWORD', 'HOST'):
            if(k not in d):
                raise ImproperlyConfigured("Required '%s' key missing from '%s' database settings." % (k, self.alias))
            elif not(d[k]):
                raise ImproperlyConfigured("'%s' key is the empty string in '%s' database settings." % (k, self.alias))

        try:
            urlparse(d['HOST'])
        except Exception as e:
            raise ImproperlyConfigured("'HOST' key in '%s' database settings should be a valid URL: %s" %
                                       (self.alias, e))

    def cursor(self, query=None):
        """
        Return a fake cursor for accessing the Salesforce API with SOQL.
        """
        from salesforce.backend.query import CursorWrapper
        cursor = CursorWrapper(self, query)
        return cursor

    def quote_name(self, name):
        """
        Do not quote column and table names in the SOQL dialect.
        """
        return name

    @property
    def is_sandbox(self):
        if self._is_sandbox is None:
            cur = self.cursor()
            cur.execute("SELECT IsSandbox FROM Organization")
            self._is_sandbox = cur.fetchone()['IsSandbox']
        return self._is_sandbox
