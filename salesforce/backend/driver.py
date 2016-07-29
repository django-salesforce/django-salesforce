"""
Dummy Salesforce driver that simulates some parts of DB API 2
"""
import socket

from django.conf import settings
from django.utils.six import PY3

try:
    import beatbox
except ImportError:
    beatbox = None

import logging
log = logging.getLogger(__name__)

apilevel = "2.0"
# threadsafety = ...

# uses '%s' style parameters
paramstyle = 'format'

# All error types described in DB API 2 are implemented the same way as in
# Django 1.6, otherwise some exceptions are not correctly reported in it.


class Error(Exception if PY3 else StandardError):
    pass


class InterfaceError(Error):
    pass


class DatabaseError(Error):
    pass


class DataError(DatabaseError):
    pass


class OperationalError(DatabaseError):
    pass


class IntegrityError(DatabaseError):
    pass


class InternalError(DatabaseError):
    pass


class ProgrammingError(DatabaseError):
    pass


class NotSupportedError(DatabaseError):
    pass


class Connection(object):
    # close and commit can be safely ignored because everything is
    # committed automatically and REST is stateles.
    def close(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        log.info("Rollback is not implemented.")


# DB API function
def connect(**params):
    return Connection()


# LOW LEVEL


def getaddrinfo_wrapper(host, port, family=socket.AF_INET, socktype=0, proto=0, flags=0):
    """Patched 'getaddrinfo' with default family IPv4 (enabled by settings IPV4_ONLY=True)"""
    return orig_getaddrinfo(host, port, family, socktype, proto, flags)

# patch to IPv4 if required and not patched by anything other yet
if getattr(settings, 'IPV4_ONLY', False) and socket.getaddrinfo.__module__ in ('socket', '_socket'):
    log.info("Patched socket to IPv4 only")
    orig_getaddrinfo = socket.getaddrinfo
    # replace the original socket.getaddrinfo by our version
    socket.getaddrinfo = getaddrinfo_wrapper
