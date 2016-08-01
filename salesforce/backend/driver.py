"""
Dummy Salesforce driver that simulates some parts of DB API 2

https://www.python.org/dev/peps/pep-0249/
should be independent on Django.db
and if possible should be independent on django.conf.settings
Code at lower level than DB API should be also here.
"""
from collections import namedtuple
import requests
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

API_STUB = '/services/data/v35.0'

request_count = 0  # global counter

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


class SalesforceError(DatabaseError):
    """
    DatabaseError that usually gets detailed error information from SF response

    in the second parameter, decoded from REST, that frequently need not to be
    displayed.
    """
    def __init__(self, message='', data=None, response=None, verbose=False):
        DatabaseError.__init__(self, message)
        self.data = data
        self.response = response
        self.verbose = verbose
        if verbose:
            log.info("Error (debug details) %s\n%s", response.text,
                     response.__dict__)


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

# ----


def handle_api_exceptions(url, f, *args, **kwargs):
    """Call REST API and handle exceptions
    Params:
        f:  requests.get or requests.post...
        _cursor: sharing the debug information in cursor
    """
    #import pdb; pdb.set_trace()
    #print("== REQUEST %s | %s | %s | %s" % (url, f, args, kwargs))
    global request_count
    # The 'verify' option is about verifying SSL certificates
    kwargs_in = {'timeout': getattr(settings, 'SALESFORCE_QUERY_TIMEOUT', 3),
                 'verify': True}
    kwargs_in.update(kwargs)
    _cursor = kwargs_in.pop('_cursor', None)
    log.debug('Request API URL: %s' % url)
    request_count += 1
    try:
        response = f(url, *args, **kwargs_in)
    # TODO some timeouts can be rarely raised as "SSLError: The read operation timed out"
    except requests.exceptions.Timeout:
        raise SalesforceError("Timeout, URL=%s" % url)
    if response.status_code == 401:
        # Unauthorized (expired or invalid session ID or OAuth)
        data = response.json()[0]
        if(data['errorCode'] == 'INVALID_SESSION_ID'):
            token = f.__self__.auth.reauthenticate()
            if('headers' in kwargs):
                kwargs['headers'].update(dict(Authorization='OAuth %s' % token))
            try:
                response = f(url, *args, **kwargs_in)
            except requests.exceptions.Timeout:
                raise SalesforceError("Timeout, URL=%s" % url)

    if response.status_code in (200, 201, 204):
        return response

    # TODO Remove this verbose setting after tuning of specific messages.
    #      Currently it is better more or less.
    # http://www.salesforce.com/us/developer/docs/api_rest/Content/errorcodes.htm
    verbose = not getattr(getattr(_cursor, 'query', None), 'debug_silent', False)
    # Errors are reported in the body
    data = response.json()[0]
    if response.status_code == 404:  # ResourceNotFound
        if (f.__func__.__name__ == 'delete') and data['errorCode'] in (
                'ENTITY_IS_DELETED', 'INVALID_CROSS_REFERENCE_KEY'):
            # It is a delete command and the object is in trash bin or
            # completely deleted or it only could be a valid Id for this type
            # then is ignored similarly to delete by a classic database query:
            # DELETE FROM xy WHERE id = 'something_deleted_yet'
            return None
        else:
            # if this Id can not be ever valid.
            raise SalesforceError("Couldn't connect to API (404): %s, URL=%s"
                                  % (response.text, url), data, response, verbose
                                  )
    if(data['errorCode'] == 'INVALID_FIELD'):
        raise SalesforceError(data['message'], data, response, verbose)
    elif(data['errorCode'] == 'MALFORMED_QUERY'):
        raise SalesforceError(data['message'], data, response, verbose)
    elif(data['errorCode'] == 'INVALID_FIELD_FOR_INSERT_UPDATE'):
        raise SalesforceError(data['message'], data, response, verbose)
    elif(data['errorCode'] == 'METHOD_NOT_ALLOWED'):
        raise SalesforceError('%s: %s' % (url, data['message']), data, response, verbose)
    # some kind of failed query
    else:
        raise SalesforceError('%s' % data, data, response, verbose)
