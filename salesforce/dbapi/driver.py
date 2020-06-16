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
import pprint
import re
import socket
import sys
import threading
import time
import warnings
from itertools import islice
from typing import (
    Any, Callable, cast, Dict, Generic, Iterable, Iterator, List, NamedTuple, Optional,
    overload, Sequence, Tuple, Type, TypeVar, Union,
)
from urllib.parse import urlencode

import pytz
import requests
from requests.adapters import HTTPAdapter

import salesforce
from salesforce.auth import SalesforceAuth, time_statistics
from salesforce.dbapi import get_max_retries
from salesforce.dbapi import settings  # i.e. django.conf.settings
from salesforce.dbapi.exceptions import (  # NOQA pylint: disable=unused-import
    Error, InterfaceError, DatabaseError, DataError, OperationalError, IntegrityError,
    InternalError, ProgrammingError, NotSupportedError, SalesforceError, SalesforceWarning,
    warn_sf,
    FakeReq, FakeResp, GenResponse)
from salesforce.dbapi.subselect import QQuery, _TRow

try:
    import beatbox  # type: ignore[import]  # pylint: disable=unused-import
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

ErrInfo = Tuple[Type[Exception], Exception]

ErrorHandler = Callable[['RawConnection', Optional['Cursor[Any]'], Type[BaseException], BaseException], None]


class SfSession(requests.Session):
    auth = None  # type: SalesforceAuth


class RawConnection:
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

    def __init__(self, settings_dict: Dict[str, Any], alias: Optional[str] = None,
                 errorhandler: Optional[ErrorHandler] = None, use_introspection: Optional[bool] = None) -> None:

        # private members:
        self.alias = cast(str, alias)
        self.errorhandler = errorhandler
        self.use_introspection = use_introspection if use_introspection is not None else True  # TODO
        self.settings_dict = settings_dict
        self.messages = []           # type: List[ErrInfo]

        self._sf_session = None      # type: Optional[SfSession]
        self._api_version = settings_dict.get('API_VERSION', salesforce.API_VERSION)  # type: str
        self.debug_verbs = None      # type: Optional[List[str]]
        self.composite_type = 'sobject-collections'  # 'sobject-collections' or 'composite'

        self.sf_auth = SalesforceAuth.create_subclass_instance(db_alias=self.alias,
                                                               settings_dict=self.settings_dict)
        # The SFDC database is connected as late as possible if only tests
        # are running. Some tests don't require a connection.
        if not getattr(settings, 'SF_LAZY_CONNECT', 'test' in sys.argv):  # TODO don't use argv
            self.make_session()

    # -- public methods

    # Methods close() and commit() can be safely ignored, because everything is
    # committed automatically and the REST API is stateless.

    @property
    def api_ver(self) -> str:
        # The highest supported SFDC API version can be set by
        # settings.DATABASES['salesforce']['API_VERSION'] = 'MAX'
        # It is useful for development of 'inspectdb'
        if self._api_version == 'MAX':
            self._api_version = self.handle_api_exceptions('GET', '', api_ver='').json()[-1]['version']
        return self._api_version

    def close(self) -> None:
        del self.messages[:]
        if self._sf_session:
            self._sf_session.close()

    def commit(self) -> None:  # pylint:disable=no-self-use
        # "Database modules that do not support transactions should implement
        # this method with void functionality."
        pass

    def rollback(self) -> None:  # pylint:disable=no-self-use
        log.info("Rollback is not implemented in Salesforce.")

    @overload
    def cursor(self) -> 'Cursor[List[Any]]': ...
    @overload  # noqa
    def cursor(self, row_type: Type[_TRow]) -> 'Cursor[_TRow]': ...

    def cursor(self, row_type=list):  # type: ignore[no-untyped-def] # noqa
        return Cursor(self, row_type)

    # -- private attributes

    @property
    def sf_session(self) -> SfSession:
        if self._sf_session is None:
            self.make_session()
            assert self._sf_session
        return self._sf_session

    def make_session(self) -> None:
        """Authenticate and get the name of assigned SFDC data server"""
        with connect_lock:
            if self._sf_session is None:
                auth_data = self.sf_auth.authenticate_and_cache()
                sf_instance_url = auth_data.get('instance_url')
                sf_session = SfSession()
                sf_session.auth = self.sf_auth
                if sf_instance_url and sf_instance_url not in sf_session.adapters:
                    # a repeated mount to the same prefix would cause a warning about unclosed SSL socket
                    sf_requests_adapter = HTTPAdapter(max_retries=get_max_retries())
                    sf_session.mount(sf_instance_url, sf_requests_adapter)
                # Additional headers work, but the same are added automatically by "requests' package.
                # sf_session.header = {'accept-encoding': 'gzip, deflate', 'connection': 'keep-alive'}
                self._sf_session = sf_session

    def rest_api_url(self, *url_parts_: str, **kwargs: Any) -> str:
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
        url_parts = list(url_parts_)
        if url_parts and re.match(r'^(?:https|mock)://', url_parts[0]):
            return '/'.join(url_parts)
        relative = kwargs.pop('relative', False)  # type: bool
        api_ver = kwargs.pop('api_ver', None)     # type: Optional[str]
        api_ver = api_ver if api_ver is not None else self.api_ver
        assert not kwargs
        if not relative:
            base = [self.sf_auth.instance_url]
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

    def handle_api_exceptions(self, method: str, *url_parts: str, **kwargs: Any) -> requests.Response:
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
        if not errorhandler:
            # nothing is caught usually and error handler not used
            return self.handle_api_exceptions_inter(method, *url_parts, **kwargs)
        else:
            try:
                return self.handle_api_exceptions_inter(method, *url_parts, **kwargs)
            except (SalesforceError, requests.exceptions.RequestException):
                exc_class, exc_value, _ = sys.exc_info()
                errorhandler(self, cursor_context, exc_class, exc_value)
                raise

    def handle_api_exceptions_inter(self, method: str, *url_parts: str, **kwargs: Any) -> requests.Response:
        """The main (middle) part - it is enough if no error occurs."""
        global request_count  # used only in single thread tests - OK # pylint:disable=global-statement
        # log.info("request %s %s", method, '/'.join(url_parts))
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
        if (response.status_code == 401                      # Unauthorized
                and 'json' in response.headers['content-type']
                and response.json()[0]['errorCode'] == 'INVALID_SESSION_ID'):
            # Reauthenticate and retry (expired or invalid session ID or OAuth)
            token = session.auth.reauthenticate()
            if token:
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
        return  # type: ignore[return-value]  # noqa

    def raise_errors(self, response: GenResponse) -> None:
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

    def handle_api_exceptions_big(self, method: str, *url_parts: str, **kwargs: Any) -> requests.Response:
        """Call REST API with the query encapsulated into the body if the query is big"""
        assert method == 'GET'
        api_ver = kwargs.pop('api_ver', None)
        url = self.rest_api_url(*url_parts, api_ver=api_ver)
        url = re.sub(r'^\w+://[^/]+', '', url)
        data = [{'method': 'GET', 'url': url, 'referenceId': 'subrequest_0'}]
        return self.composite_request(data)

    def composite_request(self, data: List[Dict[str, Any]]) -> requests.Response:
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

        bad_req = FakeReq(bad_request['method'], bad_request['url'], bad_request.get('body', ''),
                          bad_request.get('httpHeaders', {}), context={bad_i: bad_request['referenceId']})

        body = [merge_dict(x, referenceId=bad_response['referenceId'])
                for x in bad_response['body']]
        bad_resp_headers = bad_response['httpHeaders'].copy()
        bad_resp_headers.update({'Content-Type': resp.headers['Content-Type']})

        bad_resp = FakeResp(bad_response['httpStatusCode'], bad_resp_headers, json.dumps(body), bad_req
                            ) # type: requests.Response # type: ignore[assignment]  # noqa

        self.raise_errors(bad_resp)
        return  # type: ignore[return-value]  # noqa

    @staticmethod
    def _group_results(resp_data: List[Dict[str, Any]], records: Sequence[Dict[str, Any]], all_or_none: bool
                       ) -> Tuple[List[Tuple[int, Any]], List[Tuple[int, Any, Any, str]], List[Tuple[int, Any]]]:
        x_ok, x_err, x_roll = [], [], []
        for i, x in enumerate(resp_data):
            if x['success']:
                x_ok.append((i, x))
            elif x['errors'][0]['statusCode'] in ('PROCESSING_HALTED', 'ALL_OR_NONE_OPERATION_ROLLED_BACK'):
                x_roll.append((i, x))
            else:
                if isinstance(records[i], dict):
                    bad_id = [v for k, v in records[i].items() if k.lower() == 'id']
                    x_err.append((i, x['errors'], records[i]['attributes']['type'], bad_id[0] if bad_id else None))
                else:
                    x_err.append((i, x['errors'], 'unknown_type', records[i]))
        if all_or_none:
            # more errors can be reported even with all_or_none, but sometimes only the first concrete error
            assert not x_err and not x_roll or not x_ok and len(x_err) > 0
        else:
            assert not x_roll
        return x_ok, x_err, x_roll

    def sobject_collections_request(self,
                                    method: str,
                                    records: Sequence[Dict[str, Any]],
                                    all_or_none: bool = True
                                    ) -> List[str]:
        # pylint:disable=too-many-locals
        assert method in ('GET', 'POST', 'PATCH', 'DELETE')
        if method == 'DELETE':
            assert all(isinstance(x, str) for x in records)
            ids = cast(Sequence[str], records)
            params = dict(ids=','.join(ids), allOrNone=str(bool(all_or_none)).lower())
            resp = self.handle_api_exceptions(method, 'composite/sobjects', params=params)
        else:
            assert all(isinstance(x, dict) for x in records)
            if method in ('POST', 'PATCH'):
                records = [merge_dict(x, attributes={'type': x['type_']}) for x in records]
                for x in records:
                    x.pop('type_')
                post_data = {'records': records, 'allOrNone': all_or_none}
            else:
                raise NotSupportedError("Method {} not implemended".format(method))

            resp = self.handle_api_exceptions(method, 'composite/sobjects', json=post_data)
        resp_data = resp.json()

        x_ok, x_err, x_roll = self._group_results(resp_data, records, all_or_none)  # pylint:disable=unused-variable
        is_ok = not x_err
        if is_ok:
            return [x['id'] for i, x in x_ok]  # for .lastrowid

        width_type = max(len(type_) for i, errs, type_, id_ in x_err)
        width_type = max(width_type, len('sobject'))
        messages = [
            '(see details below)',
            '',
            'Error Summary: errors={}, rollback/cancel={}, success={}'.format(len(x_err), len(x_roll), len(x_ok)),
            'index {} sobject{:{width}s}error_info'.format(
                ('ID' + 16 * ' ' if x_err[0][3] else ''), '', width=(width_type + 2 - len('sobject')))
        ]
        for i, errs, type_, id_ in x_err:
            field_info = 'FIELDS: {}'.format(errs[0]['fields']) if errs[0].get('fields') else ''
            msg = '{:5d} {} {:{width_type}s}  {}: {} {}'.format(
                i, id_ or '', type_, errs[0]['statusCode'], errs[0]['message'], field_info,
                width_type=width_type)
            messages.append(msg)
        raise SalesforceError(messages)

    def ping_connection(self, timeout: float = 1.0) -> float:
        """Fast check the connection by an unimportant request

        It is useful after a longer inactivity if a connection could
        have been incorrectly terminated and can cause a timeout. This
        simple command will recreate the connection after a short timeout
        1 second, if necessary, while normal commands use a longer timeout,
        typically 30 sec.
        Returns the duration if the command succeded.
        """
        t_0 = time.time()
        try:
            self.handle_api_exceptions('GET', '', api_ver='', timeout=timeout)
        except (requests.exceptions.RequestException, SalesforceError):
            pass
        return round(time.time() - t_0, 3)


Connection = RawConnection


# DB API function
def connect(**params: Any) -> Connection:
    return Connection(**params)


def get_connection(alias: str, **params: Any) -> Connection:
    if not hasattr(thread_connections, alias):
        setattr(thread_connections, alias, connect(alias=alias, **params))
    return cast(Connection, getattr(thread_connections, alias))


class Cursor(Generic[_TRow]):
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
    def __init__(self, connection: Connection, row_type: Optional[Type[_TRow]] = None) -> None:
        # DB API attributes (public, ordered by documentation PEP 249)
        self.description = None           # type: Optional[List[Tuple[Any, ...]]]
        self.rowcount = -1  # set to non-negative by SELECT INSERT UPDATE DELETE
        self.arraysize = 1  # writable, but ignored finally
        # db api extensions
        self.rownumber = None             # type: Optional[int]  # cursor position index
        self.connection = connection
        self.messages = []                # type: List[ErrInfo]
        self.lastrowid = None  # TODO to be used for INSERT id, but insert is not implemented by cursor
        self.errorhandler = connection.errorhandler
        # private
        assert row_type in (list, dict, None)
        if row_type is None or issubclass(row_type, list):
            self.row_type = list          # type: Union[Type[Dict[str, Any]], Type[List[Any]]]
        else:
            self.row_type = row_type      # dict
        self._chunk = []                  # type: List[Dict[str, Any]]  # it is in the native JSON format
        self._chunk_offset = None         # type: Optional[int]
        self._next_records_url = None     # type: Optional[str]
        self.handle = None                # type: Optional[str]
        self.qquery = None                # type: Optional[QQuery]
        self._raw_iterator = None         # type: Optional[Iterator[Dict[str, Any]]]
        self._iter = not_executed_yet()   # type: Iterator[_TRow]

    # -- DB API methods

    # .callproc(...)  noit implemented

    def close(self) -> None:
        self._clean()

    def execute(self, soql: str, parameters: Optional[Iterable[Any]] = None, query_all: bool = False,
                tooling_api: bool = False) -> None:
        self._clean()
        parameters = parameters or []
        sqltype = soql.split(None, 1)[0].upper()
        if sqltype == 'SELECT':
            self.execute_select(soql, parameters, query_all=query_all, tooling_api=tooling_api)
        elif sqltype == 'EXPLAIN':
            assert not tooling_api
            self.execute_explain(soql, parameters, query_all=query_all)
        else:
            # INSERT UPDATE DELETE EXPLAIN
            raise ProgrammingError("Unexpected command '{}'".format(sqltype))

    def executemany(self, operation: str, seq_of_parameters: Iterable[Iterable[Any]]) -> None:
        self._clean()
        for param in seq_of_parameters:
            self.execute(operation, param)

    def fetchone(self) -> Optional[_TRow]:
        self._check_data()
        return next(self, None)

    def fetchmany(self, size: Optional[int] = None) -> List[_TRow]:
        self._check_data()
        if size is None:
            size = self.arraysize
        return list(islice(self, size))

    def fetchall(self) -> List[_TRow]:
        self._check_data()
        return list(self)

    def scroll(self, value: int, mode: str = 'relative') -> None:
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

        assert self._chunk_offset is not None and self.rownumber is not None
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

    def setinputsizes(self, sizes: Any) -> None:
        pass  # this method is allowed to do nothing

    def setoutputsize(self, size: int, column: Any = None) -> None:
        pass  # this method is allowed to do nothing

    def __next__(self) -> _TRow:
        return self._iter.__next__()

    # -- private methods

    def __iter__(self) -> 'Cursor[_TRow]':
        return self

    def _gen(self) -> Iterator[_TRow]:
        assert self._chunk_offset is not None and self.rownumber is not None
        assert self.qquery

        while True:
            self._raw_iterator = iter(self._chunk)
            for row in self.qquery.parse_rest_response(self._raw_iterator, self.rowcount,
                                                       row_type=self.row_type):
                yield cast(_TRow, row)
                self.rownumber += 1
            if not self._next_records_url:
                break
            new_offset = self._chunk_offset + len(self._chunk)
            self.query_more(self._next_records_url)
            self._chunk_offset = new_offset

    def execute_select(self, soql: str, parameters: Iterable[Any], query_all: bool = False,
                       tooling_api: bool = False) -> None:
        processed_sql = str(soql) % tuple(arg_to_soql(x) for x in parameters)
        service = '' if not tooling_api else 'tooling/'
        service += 'query' if not query_all else 'queryAll'

        self.qquery = qquery = QQuery(soql)
        # TODO better description
        self.description = [(alias, None, None, None, name) for alias, name in
                            zip(qquery.aliases, qquery.fields)]

        url_part = '/?'.join((service, urlencode(dict(q=processed_sql))))
        self.query_more(url_part)
        self._chunk_offset = 0
        self.rownumber = 0
        if self._next_records_url:
            self.handle = self._next_records_url.split('-')[0]
        self._iter = iter(self._gen())

    def execute_explain(self, soql: str, parameters: Iterable[Any], query_all: bool = False) -> None:
        # https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/dome_query_explain.htm
        self._clean()
        assert soql.startswith('EXPLAIN SELECT')
        soql = soql.split(' ', 1)[1]
        processed_sql = str(soql) % tuple(arg_to_soql(x) for x in parameters)
        service = 'query' if not query_all else 'queryAll'

        self.qquery = QQuery(soql)
        self.description = [('detail', None, None, None, 'detail')]
        url_part = '/?'.join((service, urlencode(dict(explain=processed_sql))))
        ret = self.handle_api_exceptions('GET', url_part)

        self._chunk = [{'explain': x} for x in pprint.pformat(ret.json(), indent=1, width=100).split('\n')]
        self._chunk_offset = 0
        self.rownumber = 0
        self._iter = iter(self._gen())

    def query_more(self, nextRecordsUrl: str) -> None:  # pylint:disable=invalid-name
        self._check()
        if len(nextRecordsUrl) < 15500:
            ret = self.handle_api_exceptions('GET', nextRecordsUrl).json()
        else:
            ret = self.connection.handle_api_exceptions_big('GET', nextRecordsUrl).json()
            ret = ret['compositeResponse'][0]['body']
        self.rowcount = ret['totalSize']  # may be more accurate than the initial approximate value
        self._chunk = ret['records']
        self._next_records_url = ret.get('nextRecordsUrl')

    def _check(self) -> None:
        if not self.connection:
            raise InterfaceError("Cursor Closed")

    def _check_data(self) -> None:
        if not self._iter:
            raise ProgrammingError('No previous .execute("select...") before .fetch...()')

    def _clean(self) -> None:
        self.description = None
        self.rowcount = -1
        self.rownumber = None
        del self.messages[:]
        self.lastrowid = None
        self._next_records_url = None
        self._chunk = []
        self._chunk_offset = None
        self.handle = None
        self.qquery = None
        self._raw_iterator = None
        self._iter = not_executed_yet()
        self._check()

    def handle_api_exceptions(self, method: str, *url_parts: str, **kwargs: Any) -> requests.Response:
        return self.connection.handle_api_exceptions(method, *url_parts, cursor_context=self, **kwargs)


#                              The first two items are mandatory. (name, type)
CursorDescription = NamedTuple(
    'CursorDescription', [
        ('name', str),
        ('type_code', Any),
        ('display_size', bool),
        ('internal_size', int),
        ('precision', int),
        ('scale', int),
        ('null_ok', bool),
        ('default', Any),
        ('params', dict),  # type: ignore[type-arg] # noqa
    ])
CursorDescription.__new__.__defaults__ = 7 * (None,)  # type: ignore[attr-defined]  # noqa


def standard_errorhandler(connection: Connection, cursor: Optional[Cursor[Any]], errorclass: Type[Exception],
                          errorvalue: Exception) -> None:
    if cursor:
        cursor.messages.append((errorclass, errorvalue))
    else:
        connection.messages.append((errorclass, errorvalue))


def verbose_error_handler(connection: Connection, cursor: Optional[Cursor[Any]], errorclass: Type[Exception],
                          errorvalue: Exception) -> None:  # pylint:disable=unused-argument
    pprint.pprint(errorvalue.__dict__)


# --- private


def not_executed_yet() -> Iterator[_TRow]:
    raise Connection.InterfaceError("called fetch...() before execute()")
    yield  # pylint:disable=unreachable


def signalize_extensions() -> None:
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
def getaddrinfo_wrapper(host: Any, port: Any, family: int = socket.AF_INET,
                        socktype: int = 0, proto: int = 0, flags: int = 0) -> Any:
    """Patched 'getaddrinfo' with default family IPv4 (enabled by settings IPV4_ONLY=True)"""
    return orig_getaddrinfo(host, port, family, socktype, proto, flags)
# pylint:enable=too-many-arguments


# patch to IPv4 if required and not patched by anything other yet
if getattr(settings, 'IPV4_ONLY', False) and socket.getaddrinfo.__module__ in ('socket', '_socket'):
    log.info("Patched socket to IPv4 only")
    orig_getaddrinfo = socket.getaddrinfo
    # replace the original socket.getaddrinfo by our version
    socket.getaddrinfo = cast(Any, getaddrinfo_wrapper)


# ----

# basic conversions

T = TypeVar('T')
ConversionSqlFunc = Callable[[T], Union[str, float]]
ConversionJsonFunc = Callable[[T], Optional[Union[str, float]]]


def register_conversion(type_: Type[T],
                        json_conv: ConversionJsonFunc[Any],
                        sql_conv: Optional[ConversionSqlFunc[Any]] = None,
                        subclass: bool = False
                        ) -> None:
    json_conversions[type_] = json_conv
    sql_conversions[type_] = cast(ConversionSqlFunc[Any], sql_conv or json_conv)
    if subclass and type_ not in subclass_conversions:
        subclass_conversions.append(type_)


def quoted_string_literal(txt: str) -> str:
    """
    SOQL requires single quotes to be escaped.
    http://www.salesforce.com/us/developer/docs/soql_sosl/Content/sforce_api_calls_soql_select_quotedstringescapes.htm
    """
    try:
        return "'%s'" % (txt.replace("\\", "\\\\").replace("'", "\\'"),)
    except TypeError:
        raise NotSupportedError("Cannot quote %r objects: %r" % (type(txt), txt))


def date_literal(dat: datetime.datetime) -> str:
    if not dat.tzinfo:
        tz = pytz.timezone(settings.TIME_ZONE)
        dat = tz.localize(dat, is_dst=bool(time.daylight))
    # Format of `%z` is "+HHMM"
    tzname = datetime.datetime.strftime(dat, "%z")
    return datetime.datetime.strftime(dat, "%Y-%m-%dT%H:%M:%S.000") + tzname


def arg_to_soql(arg: Any) -> Union[str, float]:
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


def arg_to_json(arg: Any) -> Optional[Union[str, float]]:
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
json_conversions = {}  # type: Dict[Type[Any], ConversionJsonFunc[Any]]

# conversion before formating a SOQL (for Select commands)
sql_conversions = {}  # type: Dict[Type[Any], ConversionSqlFunc[Any]]

subclass_conversions = []  # type: List[type]

# pylint:disable=bad-whitespace
register_conversion(int,             json_conv=str)
register_conversion(float,           json_conv=lambda o: '%.15g' % o)
register_conversion(type(None),      json_conv=lambda s: None,          sql_conv=lambda s: 'NULL')
register_conversion(str,             json_conv=lambda o: cast(str, o),  sql_conv=quoted_string_literal)  # default
register_conversion(bool,            json_conv=lambda s: str(s).lower())
register_conversion(datetime.date,   json_conv=lambda d: datetime.date.strftime(d, "%Y-%m-%d"))
register_conversion(datetime.datetime, json_conv=date_literal)
register_conversion(datetime.time,   json_conv=lambda d: datetime.time.strftime(d, "%H:%M:%S.%fZ"))
register_conversion(decimal.Decimal, json_conv=float, subclass=True)
# the type models.Model is registered from backend, because it is a Django type
# pylint:enable=bad-whitespace


def merge_dict(dict_1: Dict[Any, Any], *other: Dict[Any, Any], **kw: Any) -> Dict[Any, Any]:
    """Merge two or more dict including kw into result dict."""
    tmp = dict_1.copy()
    for x in other:
        tmp.update(x)
    tmp.update(kw)
    return tmp
