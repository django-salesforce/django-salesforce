"""
Simplified Python DB API 2.0 driver for Salesforce - (independent on Django)

https://www.python.org/dev/peps/pep-0249/

A basic SQL SELECT and a small part of PEP 0249 is currently implemented here.
Transactions will be never implemented.
SQL commands INSERT, UPDATE and DELETE could be implemented easily, but it is not
important because the current object implementation in Django is good enough.

Purpose:
Django-Salesforce is splitted to a high level part that depends on Django
(especially on a Django version) and a low level part that depends
on Salesforce API, but not on Django.
It is better for development, maintenance and testing.

This module can run without Django installed, but Django is still main purpose.
Configuration parameters are passed by `settings_dict` the same way as in Django.

The high-level public API is importable directly from this module `salesforce.dbapi`.

A connection can be created by:

    >>> from salesforce.dbapi import connect, get_connection
    >>> settings_dict = {'USER': ..., 'PASSWORD': ..., 'HOST': ...}
    >>> connect(settings_dict=settings_dict, alias=alias)

or
    >>> get_connection(alias, settings_dict=setting_dict)

or
    >>> Connection(settings_dict, alias: Optional[str] = None)

The `alias` string must be unique if more Salesforce databases are used together.
A default alias `None` is acceptable if only one connection is used.

A connection can be found by the alias later:

    >>> connection = get_connection(alias)

Or optionally the `settings_dict` can be repeated, but ignored if the connection
can be found.

Example with multiple databases:

    If we want copy some data between two Salesforce databases:

    >>> db1 = Connection({'USER': user1, 'PASSWORD': ..., 'HOST': ...}, 'salesforce')
    >>> db2 = Connection({'USER': user2, 'PASSWORD': ..., 'HOST': ...}, 'salesforce_2')


Thread safety

The driver is thread safe at DB API level 2:

    >>> threadsafety == 2  # "Threads may share the module and connections."

It is true if we consider a connection identified by an alias, however every
thread uses its own new database connections. A new connection should be opened
in a new thread again with the same `settings_dict` belonging to the same `alias`,
but a connection can not be opened again with the same alias in the same thread.
In other words, connections with the same `alias` in all threads should preferably
use the same `settings_dict`. It is similar to Django where a connection with the
same settings is opened in


Authentication:

The USER name is worldwidey unique in Salesforce SDFC and the Salesforce
database can be unambiguously identified by it.

Many static or dynamic authentication methods can be specified in `settings_dict`
by 'AUTH' key. (see `salesforce.auth` module) If a static authentication method
is used then the same 'USER' user is used in all threads all the time.

It still can be useful to modify the database data on behalf of a particular
currently logged user of a web application.
In a general case a multitenant application is possible with a dynamic
authentication where every thread can frequently switch the database and the user
associated to the `alias` according to session data of a web request. The
connection can become unauthenticated after the end of his/her request.

Threads are intended to prevent a bottle neck on a normal web server, but not
for long running batches in loop in parallel. (Salesforce could maybe reject
such a big load on REST API because a low priority high performance Bulk API
exists instead.)

--

There is also all low level code of the driver for Salesforce here in the module,
not only the DB API.
"""

import logging
from salesforce.dbapi.driver import (  # noqa pylint:disable=useless-import-alias
    Connection as Connection,
    connect as connect,
    get_connection as get_connection,
)
from salesforce.dbapi.exceptions import (  # noqa pylint:disable=useless-import-alias
    IntegrityError as IntegrityError, DatabaseError as DatabaseError, SalesforceError as SalesforceError,
    OperationalError as OperationalError,
)

log = logging.getLogger(__name__)


# -- API global constants

apilevel = "2.0"  # see https://www.python.org/dev/peps/pep-0249
threadsafety = 2

# This paramstyle uses '%s' parameters.
paramstyle = 'format'
