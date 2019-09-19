"""
Dummy Salesforce driver that simulates part of DB API 2.0

https://www.python.org/dev/peps/pep-0249/

It can run without Django installed, but still Django is the main purpose.

Low level code for Salesforce is also here.
"""
import datetime
import decimal
import json
import logging
import re
import socket
import sys
import threading
import time
import types
import warnings
import weakref
from collections import namedtuple
from itertools import islice
from typing import Optional  # NOQA

import pytz
import requests
from requests.adapters import HTTPAdapter

import salesforce
from salesforce.auth import SalesforcePasswordAuth
from salesforce.dbapi import get_max_retries
from salesforce.dbapi import settings  # i.e. django.conf.settings
from salesforce.dbapi.exceptions import (  # NOQA pylint: disable=unused-import
    Error, InterfaceError, DatabaseError, DataError, OperationalError, IntegrityError,
    InternalError, ProgrammingError, NotSupportedError, SalesforceError, SalesforceWarning,
    warn_sf, PY3, text_type)
from salesforce.dbapi.subselect import QQuery

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

try:
    import beatbox  # pylint: disable=unused-import
except ImportError:
    beatbox = None

log = logging.getLogger(__name__)

# -- API global constants

apilevel = "2.0"  # see https://www.python.org/dev/peps/pep-0249

# Every thread should use its own database connection, because waiting
# on a network connection for query response would be a bottle neck within
# REST API.

# Two thread-safety models are possible:

# Create the connection by `connect(**params)` if you use it with Django or
# with another app that has its own thread safe connection pool. and
# create the connection by connect(**params).
threadsafety = 1

# Or create and access the connection by `get_connection(alias, **params)`
# if the pool should be managed by this driver. Then you can expect:
# threadsafety = 2

# (Both variants allow multitenant architecture with dynamic authentication
# where a thread can frequently change the organization domain that it serves.)


# This paramstyle uses '%s' parameters.
paramstyle = 'format'

# --- private global constants

# Values of seconds are with 3 decimal places in SF, but they are rounded to
# whole seconds for the most of fields.
SALESFORCE_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f+0000'

# ---

request_count = 0  # global counter

connect_lock = threading.Lock()
thread_connections = threading.local()


class RawConnection(object):
    """
    parameters:
        settings_dict:  like settings.SADABASES['salesforce'] in Django
        alias:          important if the authentication should be shared for more thread
        errorhandler: function with following signature
            ``errorhandler(connection, cursor, errorclass, errorvalue)``
        use_introspection: bool
    """
    # pylint:disable=too-many-instance-attributes

    Error = Error
    InterfaceError = InterfaceError
    DatabaseError = DatabaseError
    DataError = DataError
    OperationalError = OperationalError
    IntegrityError = IntegrityError
    InternalError = InternalError
    ProgrammingError = ProgrammingError
    NotSupportedError = NotSupportedError

    def __init__(self, settings_dict, alias=None, errorhandler=None, use_introspection=None):

        # private members:
        self.alias = alias
        self.errorhandler = errorhandler
        self.use_introspection = use_introspection if use_introspection is not None else True  # TODO
        self.settings_dict = settings_dict
        self.messages = []

        self._sf_session = None
        self.api_ver = salesforce.API_VERSION
        self.debug_verbs = None
        self.composite_type = 'sobject-collections'  # 'sobject-collections' or 'composite'

        self._last_used_cursor = None  # weakref.proxy for single thread debugging

        # The SFDC database is connected as late as possible if only tests
        # are running. Some tests don't require a connection.
        if not getattr(settings, 'SF_LAZY_CONNECT', 'test' in sys.argv):  # TODO don't use argv
            self.make_session()

    # -- public methods

    # Methods close() and commit() can be safely ignored, because everything is
    # committed automatically and the REST API is stateless.

    def close(self):
        del self.messages[:]

    def commit(self):  # pylint:disable=no-self-use
        # "Database modules that do not support transactions should implement
        # this method with void functionality."
        pass

    def rollback(self):  # pylint:disable=no-self-use
        log.info("Rollback is not implemented in Salesforce.")

    def cursor(self):
        return Cursor(self)

    # -- private attributes

    @property
    def sf_session(self):
        if self._sf_session is None:
            self.make_session()
        return self._sf_session

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
                # Additional headers work, but the same are added automatically by "requests' package.
                # sf_session.header = {'accept-encoding': 'gzip, deflate', 'connection': 'keep-alive'} # TODO
                self._sf_session = sf_session

    def rest_api_url(self, *url_parts, **kwargs):
        """Join the URL of REST_API

        parameters:
            upl_parts:  strings that are joined to the url by "/".
                a REST url like https://na1.salesforce.com/services/data/v44.0/
                is usually added, but not if the first string starts with https://
            api_ver:  API version that should be used instead of connection.api_ver
                default. A special api_ver="" can be used to omit api version
                (for request to ask for available api versions)
            relative: If `relative` is true then the url is without domain
        Examples: self.rest_api_url("query?q=select+id+from+Organization")
                  self.rest_api_url("sobject", "Contact", id, api_ver="45.0")
                  self.rest_api_url(api_ver="")   # versions request
                  self.rest_api_url("sobject", relative=True)
                  self.rest_api_url("/services/data/v45.0")
        Output:

                  https://na1.salesforce.com/services/data/v44.0/query?q=select+id+from+Organization
                  https://na1.salesforce.com/services/data/v45.0/sobject/Contact/003DD00000000XYAAA
                  https://na1.salesforce.com/services/data
                  /services/data/v45.0
                  https://na1.salesforce.com/services/data/44.0
        """
        url_parts = list(url_parts)
        if url_parts and re.match(r'^(?:https|mock)://', url_parts[0]):
            return '/'.join(url_parts)
        relative = kwargs.pop('relative', False)
        api_ver = kwargs.pop('api_ver', None)
        api_ver = api_ver if api_ver is not None else self.api_ver
        assert not kwargs
        if not relative:
            base = [self.sf_session.auth.instance_url]
        else:
            base = ['']
        if url_parts and url_parts[0].startswith('/'):
            prefix = []
            url_parts[0] = url_parts[0][1:]
        else:
            prefix = ['services/data']
            if api_ver:
                prefix += ['v{api_ver}'.format(api_ver=api_ver)]
        return '/'.join(base + prefix + url_parts)

    def handle_api_exceptions(self, method, *url_parts, **kwargs):
        """Call REST API and handle exceptions
        Params:
            method:  'HEAD', 'GET', 'POST', 'PATCH' or 'DELETE'
            url_parts: like in rest_api_url() method
            api_ver:   like in rest_api_url() method
            kwargs: other parameters passed to requests.request,
                but the only notable parameter is: (... json=data)

                that works like (...
                    headers = {'Content-Type': 'application/json'},
                    data=json.dumps(data))
        """
        # The outer part - about error handler
        assert method in ('HEAD', 'GET', 'POST', 'PATCH', 'DELETE')
        cursor_context = kwargs.pop('cursor_context', None)
        errorhandler = cursor_context.errorhandler if cursor_context else self.errorhandler
        catched_exceptions = (SalesforceError, requests.exceptions.RequestException) if errorhandler else ()
        try:
            return self.handle_api_exceptions_inter(method, *url_parts, **kwargs)

        except catched_exceptions:
            # nothing is catched usually and error handler not used
            exc_class, exc_value, _ = sys.exc_info()
            errorhandler(self, cursor_context, exc_class, exc_value)
            raise

    def handle_api_exceptions_inter(self, method, *url_parts, **kwargs):
        """The main (middle) part - it is enough if no error occurs."""
        global request_count  # used only in single thread tests - OK # pylint:disable=global-statement
        # log.info("request %s %s", method, '/'.join(url_parts))
        # import pdb; pdb.set_trace()  # NOQA
        api_ver = kwargs.pop('api_ver', None)
        url = self.rest_api_url(*url_parts, api_ver=api_ver)
        # The 'verify' option is about verifying TLS certificates
        kwargs_in = {'timeout': getattr(settings, 'SALESFORCE_QUERY_TIMEOUT', (4, 15)),
                     'verify': True}
        kwargs_in.update(kwargs)
        log.debug('Request API URL: %s', url)
        request_count += 1
        session = self.sf_session

        try:
            time_statistics.update_callback(url, self.ping_connection)
            response = session.request(method, url, **kwargs_in)
        except requests.exceptions.Timeout:
            raise SalesforceError("Timeout, URL=%s" % url)
        if response.status_code == 401:  # Unauthorized
            # Reauthenticate and retry (expired or invalid session ID or OAuth)
            if ('json' in response.headers['content-type']
                    and response.json()[0]['errorCode'] == 'INVALID_SESSION_ID'):
                token = session.auth.reauthenticate()
                if 'headers' in kwargs:
                    kwargs['headers'].update(Authorization='OAuth %s' % token)
                try:
                    response = session.request(method, url, **kwargs_in)
                except requests.exceptions.Timeout:
                    raise SalesforceError("Timeout, URL=%s" % url)

        if response.status_code < 400:  # OK
            # 200 "OK" (GET, POST)
            # 201 "Created" (POST)
            # 204 "No Content" (DELETE)
            # 300 ambiguous items for external ID.
            # 304 "Not Modified" (after conditional HEADER request for metadata),
            return response
        # status codes docs (400, 403, 404, 405, 415, 500)
        # https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/errorcodes.htm
        self.raise_errors(response)

    def raise_errors(self, response):
        """The innermost part - report errors by exceptions"""
        # Errors: 400, 403 permissions or REQUEST_LIMIT_EXCEEDED, 404, 405, 415, 500)
        # TODO extract a case ID for Salesforce support from code 500 messages

        # TODO disabled 'debug_verbs' temporarily, after writing better default messages
        verb = self.debug_verbs  # NOQA pylint:disable=unused-variable
        method = response.request.method
        data = None
        is_json = 'json' in response.headers.get('Content-Type', '') and response.text
        if is_json:
            data = json.loads(response.text)
        if not (isinstance(data, list) and data and 'errorCode' in data[0]):
            messages = [response.text] if is_json else []
            raise OperationalError(
                ['HTTP error "%d %s":' % (response.status_code, response.reason)]
                + messages, response, ['method+url'])

        # Other Errors are reported in the json body
        err_msg = data[0]['message']
        err_code = data[0]['errorCode']
        if response.status_code == 404:  # ResourceNotFound
            if method == 'DELETE' and err_code in ('ENTITY_IS_DELETED', 'INVALID_CROSS_REFERENCE_KEY'):
                # It was a delete command and the object is in trash bin or it is
                # completely deleted or it could be a valid Id for this sobject type.
                # Then we accept it with a warning, similarly to delete by a classic database query:
                # DELETE FROM xy WHERE id = 'something_deleted_yet'
                warn_sf([err_msg, "Object is deleted before delete or update"], response, ['method+url'])
                # TODO add a warning and add it to messages
                return None
        if err_code in ('NOT_FOUND',           # 404 e.g. invalid object type in url path or url query?q=select ...
                        'METHOD_NOT_ALLOWED',  # 405 e.g. patch instead of post
                        ):                     # both need to report the url
            raise SalesforceError([err_msg], response, ['method+url'])
        # it is good e.g for these errorCode: ('INVALID_FIELD', 'MALFORMED_QUERY', 'INVALID_FIELD_FOR_INSERT_UPDATE')
        raise SalesforceError([err_msg], response)

    def composite_request(self, data):
        """Call a 'composite' request with subrequests, error handling

        A fake object for request/response is created for a subrequest in case
        of error, to be possible to use the same error hanler with a clear
        message as with an individual request.
        """
        post_data = {'compositeRequest': data, 'allOrNone': True}
        resp = self.handle_api_exceptions('POST', 'composite', json=post_data)
        comp_resp = resp.json()['compositeResponse']
        is_ok = all(x['httpStatusCode'] < 400 for x in comp_resp)
        if is_ok:
            return resp

        # construct an equivalent of individual bad request/response
        bad_responses = {
            i: x for i, x in enumerate(comp_resp)
            if not (x['httpStatusCode'] == 400
                    and x['body'][0]['errorCode'] in ('PROCESSING_HALTED', 'ALL_OR_NONE_OPERATION_ROLLED_BACK'))
        }
        if len(bad_responses) != 1:
            raise InternalError("Too much or too many subrequests with an individual error")
        bad_i, bad_response = bad_responses.popitem()
        bad_request = data[bad_i]

        bad_req = FakeReq(bad_request['method'], bad_request['url'], bad_request.get('body'),
                          bad_request.get('httpHeaders', {}), context={bad_i: bad_request['referenceId']})

        body = [merge_dict(x, referenceId=bad_response['referenceId'])
                for x in bad_response['body']]
        bad_resp_headers = bad_response['httpHeaders'].copy()
        bad_resp_headers.update({'Content-Type': resp.headers['Content-Type']})

        bad_resp = FakeResp(bad_response['httpStatusCode'], json.dumps(body), bad_req, bad_resp_headers)

        self.raise_errors(bad_resp)

    @staticmethod
    def _group_results(resp_data, records, all_or_none):
        x_ok, x_err, x_roll = [], [], []
        for i, x in enumerate(resp_data):
            if x['success']:
                x_ok.append((i, x))
            elif x['errors'][0]['statusCode'] in ('PROCESSING_HALTED', 'ALL_OR_NONE_OPERATION_ROLLED_BACK'):
                x_roll.append((i, x))
            else:
                bad_id = [v for k, v in records[i].items() if k.lower() == 'id']
                x_err.append((i, x['errors'], records[i]['attributes']['type'], bad_id[0] if bad_id else None))
        if all_or_none:
            assert not x_err and not x_roll or not x_ok and len(x_err) == 1
        else:
            assert not x_roll
        return x_ok, x_err, x_roll

    def sobject_collections_request(self, method, records, all_or_none=True):
        # pylint:disable=too-many-locals
        assert method in ('GET', 'POST', 'PATCH', 'DELETE')
        if method == 'DELETE':
            params = dict(ids=','.join(records), allOrNone=str(bool(all_or_none)).lower())
            resp = self.handle_api_exceptions(method, 'composite/sobjects', params=params)
        else:
            if method in ('POST', 'PATCH'):
                records = [merge_dict(x, attributes={'type': x['type_']}) for x in records]
                for x in records:
                    x.pop('type_')
                post_data = {'records': records, 'allOrNone': all_or_none}
            else:
                raise NotSupportedError("Method {} not implemended".format(method))

            resp = self.handle_api_exceptions(method, 'composite/sobjects', json=post_data)
        resp_data = resp.json()

        x_ok, x_err, x_roll = self._group_results(resp_data, records, all_or_none)
        is_ok = not x_err
        if is_ok:
            return [x['id'] for i, x in x_ok]  # for .lastrowid

        width_type = max(len(type_) for i, errs, type_, id_ in x_err)
        width_type = max(width_type, len('sobject'))
        messages = ['', 'index {} sobject{:{width}s}error_info'.format(
            ('ID' + 16 * ' ' if x_err[0][3] else ''), '', width=(width_type + 2 - len('sobject')))]
        for i, errs, type_, id_ in x_err:
            field_info = 'FIELDS: {}'.format(errs[0]['fields']) if errs[0].get('fields') else ''
            msg = '{:5d} {} {:{width_type}s}  {}: {} {}'.format(
                i, id_ or '', type_, errs[0]['statusCode'], errs[0]['message'], field_info,
                width_type=width_type)
            messages.append(msg)
        raise SalesforceError(messages)

    @property
    def last_used_cursor(self):
        try:
            return self._last_used_cursor()  # pylint:disable=not-callable
        except NameError:
            return None

    @last_used_cursor.setter
    def last_used_cursor(self, cursor):
        self._last_used_cursor = weakref.proxy(cursor)

    def ping_connection(self, timeout=1.0):  # type: (float) -> Optional[float]
        """Fast check the connection by an unimportant request

        It is useful after a longer inactivity if a connection could
        have been incorrectly terminated and can cause a timeout. This
        simple command will recreate the connection after a short timeout
        1 second, if necessary, while normal commands use a longer timeout,
        typically 30 sec.
        Returns the duration if the command succeded.
        """
        t_0 = time.time()
        self.handle_api_exceptions('GET', '', api_ver='', timeout=timeout)
        return round(time.time() - t_0, 3)


class FakeReq(object):
    # pylint:disable=too-few-public-methods,too-many-arguments
    def __init__(self, method, url, data, headers=None, context=None):
        self.method = method
        self.url = url
        self.data = data
        self.headers = headers
        self.context = context


class FakeResp(object):  # pylint:disable=too-few-public-methods,too-many-instance-attributes
    def __init__(self, status_code, headers, text, request):
        self.status_code = status_code
        self.text = text
        self.request = request
        self.headers = headers


Connection = RawConnection


# DB API function
def connect(**params):
    return Connection(**params)


def get_connection(alias, **params):
    if not hasattr(thread_connections, alias):
        setattr(thread_connections, alias, connect(alias=alias, **params))
    return getattr(thread_connections, alias)


class Cursor(object):
    """Cursor (local part is simple, remote part is stateless for small result sets)

    From SDFC documentation (combined from SOQL, REST, APEX)
    Query results are returned from SFDC by blocks of 2000 rows, by default.
    It is guaranted that the size of result block is not smaller than 200 rows,
    and not longer than 2000 rows.
    - A maximum of 10 open locators per user are available. The oldest locator
      (cursor) is deleted then by SFDC.
    - Query locators older than 15 minutes are deleted. (usually after much longer time)
    - The query locator works without transactions
    and it should be expected that the data after 2000 rows could be affected by
    later updates and may not match the `where` condition.

    The local part of the cursor is only an index into the last block of 2000
    rows. The number of local cursors is unrestricted.

    Queries with binary fields Base64 (e.g. attachments) are returned by one row.
    the best it to get more rows without binary fields and then to query
    for complete rows, one by one.
    """

    # pylint:disable=too-many-instance-attributes
    def __init__(self, connection):
        # DB API attributes (public, ordered by documentation PEP 249)
        self.description = None
        self.rowcount = -1  # set to non-negative by SELECT INSERT UPDATE DELETE
        self.arraysize = 1  # writable, but ignored finally
        # db api extensions
        self.rownumber = None  # cursor position index
        self.connection = connection
        self.messages = []
        self.lastrowid = None  # used for INSERT id
        self.errorhandler = connection.errorhandler
        # private
        self.row_factory = lambda x: x  # standard dict
        self._chunk = not_executed_yet()
        self._chunk_offset = None
        self._next_records_url = None
        self.handle = None
        self.qquery = None
        self._raw_iterator = None
        self._iter = None

    # -- DB API methods

    # .callproc(...)  noit implemented

    def close(self):
        self._clean()

    def execute(self, soql, parameters=None, query_all=False):
        self._clean()
        parameters = parameters or []
        sqltype = soql.split(None, 1)[0].upper()
        if sqltype == 'SELECT':
            self.execute_select(soql, parameters, query_all=query_all)
        else:
            # INSERT UPDATE DELETE EXPLAIN
            raise ProgrammingError("Unexpected command '{}'".format(sqltype))

    def executemany(self, operation, seq_of_parameters):
        self._clean()
        for param in seq_of_parameters:
            self.execute(operation, param)

    def fetchone(self):
        self._check_data()
        return next(self, None)

    def fetchmany(self, size=None):
        self._check_data()
        if size is None:
            size = self.arraysize
        return list(islice(self, size))

    def fetchall(self):
        self._check_data()
        return list(self)

    def scroll(self, value, mode='relative'):
        # TODO It is a beta based on an undocumented information
        # The undocumented structure of 'nextRecordsUrl' is
        #     'query/{query_id}-{offset}'  e.g.
        #     '/services/data/v44.0/query/01gM000000zr0N0IAI-3012'
        warnings.warn("cursor.scroll is based on an undocumented info. Long "
                      "jump in a big query may be unsupported.")
        assert mode in ('absolute', 'relative')
        # The possible offset range is from 0 to resp.json()['totalSize']
        # An exception IndexError should be raised if the offset is invalid [PEP 429]
        # but this will simply pass the original exception from SFDC:
        # "SalesforceError: INVALID_QUERY_LOCATOR"

        new_offset = int(value) + (0 if mode == 'absolute' else self.rownumber)
        if not self._chunk_offset <= new_offset < self._chunk_offset + len(self._chunk):
            url = '{}-{}'.format(self.handle, new_offset)
            self.query_more(url)
            self._chunk_offset = new_offset
        self._raw_iterator = iter(self._chunk)
        if new_offset != self._chunk_offset:
            rel_offs = new_offset - self._chunk_offset
            next(islice(self._raw_iterator, rel_offs, rel_offs), None)
        self.rownumber = new_offset
        self._iter = iter(self._gen())

    # .nextset()  not implemented

    def setinputsizes(self, sizes):
        pass  # this method is allowed to do nothing

    def setoutputsize(self, size, column=None):
        pass  # this method is allowed to do nothing

    def __next__(self):
        return next(self._iter)

    next = __next__  # Python 2

    # -- private methods

    def __iter__(self):
        return self

    def _gen(self):
        while True:
            self._raw_iterator = iter(self._chunk)
            for row in self.qquery.parse_rest_response(self._raw_iterator, self.rowcount):
                yield self.row_factory(row)
                self.rownumber += 1
            if not self._next_records_url:
                break
            new_offset = self._chunk_offset + len(self._chunk)
            self.query_more(self._next_records_url)
            self._chunk_offset = new_offset

    def execute_select(self, soql, parameters, query_all=False):
        processed_sql = str(soql) % tuple(arg_to_soql(x) for x in parameters)
        service = 'query' if not query_all else 'queryAll'

        self.qquery = QQuery(soql)
        # TODO better description
        self.description = [(alias, None, None, None, name) for alias, name in
                            zip(self.qquery.aliases, self.qquery.fields)]

        url_part = '?'.join((service, urlencode(dict(q=processed_sql))))
        self.query_more(url_part)
        self._chunk_offset = 0
        self.rownumber = 0
        if self._next_records_url:
            self.handle = self._next_records_url.split('-')[0]
        self._iter = iter(self._gen())

    def query_more(self, nextRecordsUrl):  # pylint:disable=invalid-name
        self._check()
        ret = self.handle_api_exceptions('GET', nextRecordsUrl).json()
        self.rowcount = ret['totalSize']  # may be more accurate than the initial approximate value
        self._chunk = ret['records']
        self._next_records_url = ret.get('nextRecordsUrl')

    def _check(self):
        if not self.connection:
            raise InterfaceError("Cursor Closed")
        self.connection.last_used_cursor = self  # it is set into weakref

    def _check_data(self):
        if not self._iter:
            raise ProgrammingError('No previous .execute("select...") before .fetch...()')

    def _clean(self):
        self.description = None
        self.rowcount = -1
        self.rownumber = None
        del self.messages[:]
        self.lastrowid = None
        self._next_records_url = None
        self._chunk = not_executed_yet()
        self._chunk_offset = None
        self.handle = None
        self.qquery = None
        self._raw_iterator = None
        self._iter = None
        self._check()

    def handle_api_exceptions(self, method, *url_parts, **kwargs):
        return self.connection.handle_api_exceptions(method, *url_parts, cursor_context=self, **kwargs)


#                              The first two items are mandatory. (name, type)
CursorDescription = namedtuple('CursorDescription', 'name type_code '
                               'display_size internal_size precision scale null_ok')
CursorDescription.__new__.func_defaults = 7 * (None,)


def standard_errorhandler(connection, cursor, errorclass, errorvalue):
    if cursor:
        cursor.messages.append((errorclass, errorvalue))
    else:
        connection.messages.append((errorclass, errorvalue))


def verbose_error_handler(connection, cursor, errorclass, errorvalue):  # pylint:disable=unused-argument
    import pprint
    pprint.pprint(errorvalue.__dict__)


# --- private


def not_executed_yet():
    raise Connection.InterfaceError("called fetch...() before execute()")
    yield  # pylint:disable=unreachable


def signalize_extensions():
    """DB API 2.0 extension are reported by warnings at run-time."""
    warnings.warn("DB-API extension cursor.rownumber used", SalesforceWarning)
    warnings.warn("DB-API extension connection.<exception> used", SalesforceWarning)  # TODO
    warnings.warn("DB-API extension cursor.connection used", SalesforceWarning)
    # not implemented DB-API extension cursor.scroll(, SalesforceWarning)
    warnings.warn("DB-API extension cursor.messages used", SalesforceWarning)
    warnings.warn("DB-API extension connection.messages used", SalesforceWarning)
    warnings.warn("DB-API extension cursor.next(, SalesforceWarning) used")
    warnings.warn("DB-API extension cursor.__iter__(, SalesforceWarning) used")
    warnings.warn("DB-API extension cursor.lastrowid used", SalesforceWarning)
    warnings.warn("DB-API extension .errorhandler used", SalesforceWarning)


# --  LOW LEVEL


# pylint:disable=too-many-arguments
def getaddrinfo_wrapper(host, port, family=socket.AF_INET, socktype=0, proto=0, flags=0):
    """Patched 'getaddrinfo' with default family IPv4 (enabled by settings IPV4_ONLY=True)"""
    return orig_getaddrinfo(host, port, family, socktype, proto, flags)
# pylint:enable=too-many-arguments


# patch to IPv4 if required and not patched by anything other yet
if getattr(settings, 'IPV4_ONLY', False) and socket.getaddrinfo.__module__ in ('socket', '_socket'):
    log.info("Patched socket to IPv4 only")
    orig_getaddrinfo = socket.getaddrinfo
    # replace the original socket.getaddrinfo by our version
    socket.getaddrinfo = getaddrinfo_wrapper


# ----

# basic conversions


def register_conversion(type_, json_conv, sql_conv=None, subclass=False):
    json_conversions[type_] = json_conv
    sql_conversions[type_] = sql_conv or json_conv
    if subclass and type_ not in subclass_conversions:
        subclass_conversions.append(type_)


def quoted_string_literal(txt):
    """
    SOQL requires single quotes to be escaped.
    http://www.salesforce.com/us/developer/docs/soql_sosl/Content/sforce_api_calls_soql_select_quotedstringescapes.htm
    """
    try:
        return "'%s'" % (txt.replace("\\", "\\\\").replace("'", "\\'"),)
    except TypeError:
        raise NotSupportedError("Cannot quote %r objects: %r" % (type(txt), txt))


def date_literal(dat):
    if not dat.tzinfo:
        tz = pytz.timezone(settings.TIME_ZONE)
        dat = tz.localize(dat, is_dst=time.daylight)
    # Format of `%z` is "+HHMM"
    tzname = datetime.datetime.strftime(dat, "%z")
    return datetime.datetime.strftime(dat, "%Y-%m-%dT%H:%M:%S.000") + tzname


def arg_to_soql(arg):
    """
    Perform necessary SOQL quoting on the arg.
    """
    conversion = sql_conversions.get(type(arg))
    if conversion:
        return conversion(arg)
    for type_ in subclass_conversions:
        if isinstance(arg, type_):
            return sql_conversions[type_](arg)
    return sql_conversions[str](arg)


def arg_to_json(arg):
    """
    Perform necessary JSON conversion on the arg.
    """
    conversion = json_conversions.get(type(arg))
    if conversion:
        return conversion(arg)
    for type_ in subclass_conversions:
        if isinstance(arg, type_):
            return json_conversions[type_](arg)
    return json_conversions[str](arg)


# supported types converted from Python to SFDC

# conversion before conversion to json (for Insert and Update commands)
json_conversions = {}

# conversion before formating a SOQL (for Select commands)
sql_conversions = {}

subclass_conversions = []

# pylint:disable=bad-whitespace
register_conversion(int,             json_conv=str)
register_conversion(float,           json_conv=lambda o: '%.15g' % o)
register_conversion(type(None),      json_conv=lambda s: None,          sql_conv=lambda s: 'NULL')
register_conversion(str,             json_conv=lambda o: o,             sql_conv=quoted_string_literal)  # default
register_conversion(bool,            json_conv=lambda s: str(s).lower())
register_conversion(datetime.date,   json_conv=lambda d: datetime.date.strftime(d, "%Y-%m-%d"))
register_conversion(datetime.datetime, json_conv=date_literal)
register_conversion(datetime.time,   json_conv=lambda d: datetime.time.strftime(d, "%H:%M:%S.%fZ"))
register_conversion(decimal.Decimal, json_conv=float, subclass=True)
# the type models.Model is registered from backend, because it is a Django type
# pylint:enable=bad-whitespace

if not PY3:
    # pylint:disable=no-member
    register_conversion(types.LongType, json_conv=str)
    register_conversion(types.UnicodeType,
                        json_conv=lambda s: s.encode('utf8'),
                        sql_conv=lambda s: quoted_string_literal(s.encode('utf8')))


def merge_dict(dict_1, *other, **kw):
    """Merge two or more dict including kw into result dict."""
    tmp = dict_1.copy()
    for x in other:
        tmp.update(x)
    tmp.update(kw)
    return tmp


class TimeStatistics(object):

    def __init__(self, expiration=300):
        self.expiration = expiration
        self.data = {}

    def update_callback(self, url, callback=None):
        """Update the statistics for the domain"""
        domain = self.domain(url)
        last_req = self.data.get(domain, 0)
        t_new = time.time()
        do_call = (t_new - last_req > self.expiration)
        self.data[domain] = t_new
        if do_call and callback:
            callback()

    @staticmethod
    def domain(url):
        match = re.match(r'^(?:https|mock)://([^/]+)/?', url)
        return match.groups()[0]


time_statistics = TimeStatistics(300)
