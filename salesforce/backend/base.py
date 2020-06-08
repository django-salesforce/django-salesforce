# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce database backend for Django.  (like django,db.backends.*.base)
"""

from typing import Any, Dict, Optional, TYPE_CHECKING

from django.conf import settings
from django.db.backends.base.base import BaseDatabaseWrapper

from salesforce.backend.client import DatabaseClient
from salesforce.backend.creation import DatabaseCreation
from salesforce.backend.features import DatabaseFeatures
from salesforce.backend.validation import DatabaseValidation
from salesforce.backend.operations import DatabaseOperations
from salesforce.backend.introspection import DatabaseIntrospection
from salesforce.backend.schema import DatabaseSchemaEditor
# from django.db.backends.signals import connection_created
from salesforce.backend.utils import CursorWrapper, async_unsafe
from salesforce.dbapi import driver as Database
from salesforce.dbapi.driver import IntegrityError, DatabaseError, SalesforceError  # NOQA pylint:disable=unused-import

if TYPE_CHECKING:
    from django.db.backends.base.base import ProtoCursor


__all__ = ('DatabaseWrapper', 'DatabaseError', 'SalesforceError',)


class DatabaseWrapper(BaseDatabaseWrapper):
    """
    Core class that provides all DB support.
    """
    # pylint:disable=abstract-method,too-many-instance-attributes
    #     undefined abstract methods: _start_transaction_under_autocommit, is_usable

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
    SchemaEditorClass = DatabaseSchemaEditor  # type: ignore[assignment] # noqa # this is normal in Django

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

        self._is_sandbox = None  # type: Optional[bool]

    @property
    def sf_session(self) -> Database.SfSession:
        if self.connection is None:
            self.connect()
            assert self.connection
        return self.connection.sf_session

    def get_connection_params(self) -> Dict[str, Any]:
        settings_dict = self.settings_dict
        params = settings_dict.copy()
        params.update(settings_dict['OPTIONS'])
        return params

    @async_unsafe
    def get_new_connection(self, conn_params: Dict[str, Any]) -> Database.RawConnection:
        # simulated only a connection interface without connecting really
        return Database.connect(settings_dict=conn_params, alias=self.alias)

    def init_connection_state(self):
        pass  # nothing to init

    def _set_autocommit(self, autocommit):
        # SF REST API uses autocommit, but until rollback it is not a
        # serious problem to ignore autocommit off
        pass

    @async_unsafe
    def cursor(self) -> Any:
        """
        Return a fake cursor for accessing the Salesforce API with SOQL.
        """
        return CursorWrapper(self)

    def create_cursor(self, name: Optional[str] = None) -> 'ProtoCursor':
        row_type = {'dict': dict, 'list': list, None: None}[name]
        return self.connection.cursor(row_type=row_type)

    def quote_name(self, name: str) -> str:
        """
        Do not quote column and table names in the SOQL dialect.
        """
        # pylint:disable=no-self-use
        return name

    @property
    def is_sandbox(self) -> bool:
        if self._is_sandbox is None:
            cur = self.cursor()
            cur.execute("SELECT IsSandbox FROM Organization")
            self._is_sandbox = cur.fetchone()[0]
        return self._is_sandbox

    def close(self) -> None:
        if self.connection:
            self.connection.close()
