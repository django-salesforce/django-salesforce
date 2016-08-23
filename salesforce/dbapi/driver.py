"""
Dummy Salesforce driver that simulates some parts of DB API 2

https://www.python.org/dev/peps/pep-0249/
should be independent on Django.db
and if possible should be independent on django.conf.settings
Code at lower level than DB API should be also here.
"""
from collections import namedtuple
from itertools import islice
import datetime
import decimal
import json
import logging
import re
import requests
import socket
import time
# import weakref

import pytz

from django.conf import settings
from django.db.models.sql import subqueries

from salesforce import models
from salesforce.dbapi.exceptions import (
    Error, DatabaseError, DataError, IntegrityError,
    InterfaceError, InternalError, NotSupportedError,
    OperationalError, ProgrammingError, SalesforceError,
    PY3
)
from salesforce.backend.subselect import QQuery
import salesforce

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode


log = logging.getLogger(__name__)

apilevel = "2.0"
# threadsafety = ...

# uses '%s' style parameters
paramstyle = 'format'

request_count = 0  # global counter

log = logging.getLogger(__name__)


def standard_errorhandler(connection, cursor, errorclass, errorvalue):
    "The errorhandler can be also used for warnings reporting"
    if cursor:
        cursor.messages.append(errorclass, errorvalue)
    elif connection:
        connection.messages.append(errorclass, errorvalue)
    else:
        pass  # maybe raise special
    if isinstance(errorclass, Error) and (isinstance(errorclass, InterfaceError) or
                                          filter(errorclass, errorvalue)):
        raise errorclass(errorvalue)
# ---


CursorDescription = namedtuple(
    'CursorDescription',
    'name, type_code, display_size, internal_size, precision, scale, null_ok'
)

# def date(year, month, day):
#    return datetime.date(year, month, day)
#
# def time(hour, minute, second):
#    return datetime.time(hour, minute, second)
#
# def timestamp(year, month, day, hour, minute, second):
#    return datetime.datetime(year, month, day, hour, minute, second)
#
# def DateFromTicks(ticks):
#     return Date(*time.localtime(ticks)[:3])
#
# def TimeFromTicks(ticks):
#     return Time(*time.localtime(ticks)[3:6])
#
# def TimestampFromTicks(ticks):
#     return Timestamp(*time.localtime(ticks)[:6])
#
# class DBAPITypeObject:
#     def __init__(self,*values):
#         self.values = values
#     def __cmp__(self,other):
#         if other in self.values:
#             return 0
#         if other < self.values:
#             return 1
#         else:
#             return -1

TODO = ['TODO']


class Cursor(object):

    # DB API methods  (except private "_*" names)

    def __init__(self, connection):
        # DB API attributes
        self.description = None
        self.rowcount = None
        self.lastrowid = None
        self.messages = []
        # static
        self.arraysize = 1
        # other
        self.connection = connection
        # self.connection = weakref.proxy(connection)

    def err_hand(self, errorclass, errorvalue):
        "call the errorhandler"
        self.connection.errorhandler(self.connection, self.cursor, errorclass, errorvalue)

    def _check(self):
        if not self.connection:
            raise InterfaceError("Cursor Closed")

    def _clean(self):
        self.description = None
        self.rowcount = -1
        self.lastrowid = None
        self.messages = []
        self._check()

    def close(self):
        self.connection = None

    def execute(self, sql, parameters):
        self._clean()
        self.rowcount = None
        sqltype = re.match(r'\s*(SELECT|INSERT|UPDATE|DELETE)\b', sql, re.I).group().upper()
        # TODO
        if sqltype == 'SELECT':
            self.qquery = QQuery(sql)
            self.description = [(alias, None, None, None, name) for alias, name in
                                zip(self.qquery.aliases, self.qquery.fields)]
            cur = CursorWrapper(self.connection)
            self.resp = cur.execute_select(sql, parameters)
            self.iterator = self.qquery.parse_rest_response(self.resp, self)
            # pdb.set_trace()
            self.rowcount = self.resp.json(parse_float=decimal.Decimal)['totalSize']
        else:
            import pdb; pdb.set_trace()
            pass

    def executemany(self, sql, seq_of_parameters):
        self._clean()
        for param in seq_of_parameters:
            self.execute(sql, param)

    def __iter__(self):
        for x in self.iterator:
            import pdb; pdb.set_trace()
            yield x

    def fetchone(self):
        self._check()
        return next(self.iterator)

    def fetchmany(self, size=None):
        # size by SF
        # size = size or cursor.arraysize
        self._check()
        return list(islice(self.iterator, size or 100))

    def fetchall(self):
        self._check()
        return list(self.iterator)

    def setinputsizes(self):
        pass

    def setoutputsize(size, column=None):
        pass

    # other methods

        #   (name=,         # req
        #   type_code=,     # req
        #   display_size=,
        #   internal_size=,
        #   precision=,
        #   scale=,
        #   null_ok=)


# fix dep subqueries type
class CursorWrapper(object):
    """
    A wrapper that emulates the behavior of a database cursor.

    This is the class that is actually responsible for making connections
    to the SF REST API
    """
    # This can be used to disable SOAP API for bulk operations even if beatbox
    # is installed and use REST API Bulk requests (Useful for tests, but worse
    # than SOAP especially due to governor limits.)
    use_soap_for_bulk = True

    def __init__(self, db, query=None):
        """
        Connect to the Salesforce API.
        """
        import salesforce.utils
        self.db = db
        self.query = query
        self.session = db.sf_session
        # A consistent value of empty self.results after execute will be `iter([])`
        self.results = None
        self.rowcount = None
        self.first_row = None
        self.row_type = list
        if salesforce.dbapi.beatbox is None:
            self.use_soap_for_bulk = False

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    @property
    def oauth(self):
        return self.session.auth.get_auth()

    def set_row_factory(self, row_type):
        """Set the row type to dict or list"""
        assert issubclass(row_type, (dict, list))
        if self.results:
            raise NotSupportedError("Method set_row_factory can be used only on a new cursor.")
        self.row_type = row_type

    # fix dep subqueries type
    def execute(self, sql, args=()):
        """
        Send a query to the Salesforce API.
        """
        self.rowcount = None
        self.db.last_chunk_len = None
        sqltype = re.match(r'\s*(SELECT|INSERT|UPDATE|DELETE)\b', sql, re.I).group().upper()
        if sqltype == 'SELECT':
            self.qquery = QQuery(sql)
            self.description = [(alias, None, None, None, name) for alias, name in
                                zip(self.qquery.aliases, self.qquery.fields)]
            response = self.execute_select(sql, args)
            data = response.json(parse_float=decimal.Decimal)
            if 'totalSize' in data:
                self.rowcount = data['totalSize']
                if sql.upper().startswith('SELECT COUNT() FROM'):
                    # COUNT() queries in SOQL are a special case, as they don't actually return rows
                    self.results = iter([[self.rowcount]])
                else:
                    if self.query:
                        self.query.last_chunk_len = len(data['records'])
                    self.first_row = data['records'][0] if data['records'] else None
                    self.results = self.qquery.parse_rest_response(response, self, self.row_type)
            else:
                raise DatabaseError(data)
        elif sqltype in ('INSERT', 'UPDATE', 'DELETE'):
            if isinstance(self.query, subqueries.InsertQuery):
                response = self.execute_insert(self.query)
            elif isinstance(self.query, subqueries.UpdateQuery):
                response = self.execute_update(self.query)
            elif isinstance(self.query, subqueries.DeleteQuery):
                response = self.execute_delete(self.query)

            if response and isinstance(response, list):
                # bulk operation SOAP
                if all(x['success'] for x in response):
                    self.lastrowid = [item['id'] for item in response]
            # the encoding is detected automatically, e.g. from headers
            elif(response and response.text):
                # parse_float set to decimal.Decimal to avoid precision errors when
                # converting from the json number to a float and then to a Decimal object
                # on a model's DecimalField. This converts from json number directly
                # to a Decimal object
                data = response.json(parse_float=decimal.Decimal)
                if('success' in data and 'id' in data):
                    self.lastrowid = data['id']
                    return
                elif data['hasErrors'] is False:
                    # save id from bulk_create even if Django don't use it
                    if data['results'] and data['results'][0]['result']:
                        self.lastrowid = [item['result']['id'] for item in data['results']]
                    return
                # something we don't recognize
                else:
                    raise DatabaseError(data)
            else:
                self.results = iter([])
        else:
            raise DatabaseError("Unsupported query: type %s: %s" % (type(self.query), self.query))

    def execute_select(self, q, args):
        processed_sql = str(q) % tuple(arg_to_soql(x) for x in args)
        service = 'query' if not getattr(self.query, 'is_query_all', False) else 'queryAll'
        url = rest_api_url(self.session, service, '?' + urlencode(dict(q=processed_sql)))
        log.debug(processed_sql)
        return handle_api_exceptions(url, self.session.get, _cursor=self)

    def query_more(self, nextRecordsUrl):
        url = u'%s%s' % (self.session.auth.instance_url, nextRecordsUrl)
        return handle_api_exceptions(url, self.session.get, _cursor=self)

    def execute_insert(self, query):
        table = query.model._meta.db_table
        headers = {'Content-Type': 'application/json'}
        post_data = extract_values(query)
        if len(post_data) == 1:
            # single object
            url = rest_api_url(self.session, 'sobjects', table, '')
            post_data = post_data[0]
        elif not self.use_soap_for_bulk:
            # bulk by REST
            url = rest_api_url(self.session, 'composite/batch')
            post_data = {
                'batchRequests': [{'method': 'POST',
                                   'url': 'v{0}/sobjects/{1}'.format(salesforce.API_VERSION,
                                                                     table),
                                   'richInput': row
                                   }
                                  for row in post_data
                                  ]
            }
        else:
            # bulk by SOAP
            svc = salesforce.utils.get_soap_client('salesforce')
            for x in post_data:
                x.update({'type': table})
            ret = svc.create(post_data)
            return ret

        log.debug('INSERT %s%s' % (table, post_data))
        return handle_api_exceptions(url, self.session.post, headers=headers, data=json.dumps(post_data), _cursor=self)

    # tix dep query...
    def execute_update(self, query):
        table = query.model._meta.db_table
        # this will break in multi-row updates
        assert (len(query.where.children) == 1 and
                query.where.children[0].lookup_name in ('exact', 'in') and
                query.where.children[0].lhs.target.column == 'Id')
        pk = query.where.children[0].rhs
        assert pk
        headers = {'Content-Type': 'application/json'}
        post_data = extract_values(query)
        log.debug('UPDATE %s(%s)%s' % (table, pk, post_data))
        if isinstance(pk, (tuple, list, salesforce.backend.query.SalesforceQuerySet)):
            if not self.use_soap_for_bulk:
                # bulk by REST
                url = rest_api_url(self.session, 'composite/batch')
                last_mod = None
                if pk and hasattr(pk[0], 'pk'):
                    last_mod = max(getattr(x, fld.name)
                                   for x in pk if hasattr(x, 'pk')
                                   for fld in x._meta.fields if fld.db_column == 'LastModifiedDate'
                                   )
                if last_mod is None:
                    last_mod = datetime.datetime.utcnow()
                post_data = {
                    'batchRequests': [{'method': 'PATCH',
                                       'url': 'v{0}/sobjects/{1}/{2}'.format(salesforce.API_VERSION,
                                                                             table,
                                                                             getattr(x, 'pk', x)),
                                       'richInput': post_data
                                       }
                                      for x in pk
                                      ]
                }
                headers.update({'If-Unmodified-Since': time.strftime('%a, %d %b %Y %H:%M:%S GMT',
                               (last_mod + datetime.timedelta(seconds=0)).timetuple())})
                _ret = handle_api_exceptions(url, self.session.post, headers=headers, data=json.dumps(post_data),
                                             _cursor=self)
            else:
                # bulk by SOAP
                svc = salesforce.utils.get_soap_client('salesforce')
                out = []
                for x in pk:
                    d = post_data.copy()
                    d.update({'type': table, 'Id': getattr(x, 'pk', x)})
                    out.append(d)
                ret = svc.update(out)
                return ret
        else:
            # single request
            url = rest_api_url(self.session, 'sobjects', table, pk)
            _ret = handle_api_exceptions(url, self.session.patch, headers=headers, data=json.dumps(post_data),
                                         _cursor=self)
        self.rowcount = 1
        return _ret

    def execute_delete(self, query):
        table = query.model._meta.db_table

        # the root where node's children may itself have children..
        def recurse_for_pk(children):
            for node in children:
                if hasattr(node, 'rhs'):
                    pk = node.rhs[0]
                else:
                    try:
                        pk = node[-1][0]
                    except TypeError:
                        pk = recurse_for_pk(node.children)
                return pk
        pk = recurse_for_pk(self.query.where.children)
        assert pk
        url = rest_api_url(self.session, 'sobjects', table, pk)

        log.debug('DELETE %s(%s)' % (table, pk))
        ret = handle_api_exceptions(url, self.session.delete, _cursor=self)
        self.rowcount = 1 if (ret and ret.status_code == 204) else 0
        return ret

    # The following 3 methods (execute_ping, id_request, versions_request)
    # can be renamed soon or moved.

    def urls_request(self):
        """Empty REST API request is useful after long inactivity before POST.

        It ensures that the token will remain valid for at least half life time
        of the new token. Otherwise it would be an awkward doubt if a timeout on
        a lost connection is possible together with token expire in a post
        request (insert).
        """
        url = rest_api_url(self.session, '')
        ret = handle_api_exceptions(url, self.session.get, _cursor=self)
        return str_dict(ret.json())

    def id_request(self):
        """The Force.com Identity Service (return type dict of text_type)"""
        # https://developer.salesforce.com/page/Digging_Deeper_into_OAuth_2.0_at_Salesforce.com?language=en&language=en#The_Force.com_Identity_Service
        if 'id' in self.oauth:
            url = self.oauth['id']
        else:
            # dynamic auth without 'id' parameter
            url = self.urls_request()['identity']
        ret = handle_api_exceptions(url, self.session.get, _cursor=self)
        return ret.json()

    def versions_request(self):
        """List Available REST API Versions"""
        url = self.session.auth.instance_url + '/services/data/'
        ret = handle_api_exceptions(url, self.session.get, _cursor=self)
        return [str_dict(x) for x in ret.json()]

    def query_results(self, results):
        while True:
            for rec in results['records']:
                if rec['attributes']['type'] == 'AggregateResult' and hasattr(self.query, 'annotation_select'):
                    annotation_select = self.query.annotation_select
                    assert len(rec) - 1 == len(list(annotation_select.items()))
                    # The 'attributes' info is unexpected for Django within fields.
                    rec = [rec[k] for k, _ in annotation_select.items()]
                yield rec

            if results['done']:
                break

            # see about Retrieving the Remaining SOQL Query Results
            # http://www.salesforce.com/us/developer/docs/api_rest/Content/dome_query.htm#retrieve_remaining_results_title
            response = self.query_more(results['nextRecordsUrl'])
            results = response.json(parse_float=decimal.Decimal)

    def __iter__(self):
        return iter(self.results)

    def fetchone(self):
        """
        Fetch a single result from a previously executed query.
        """
        try:
            return next(self.results)
        except StopIteration:
            return None

    def fetchmany(self, size=None):
        """
        Fetch multiple results from a previously executed query.
        """
        if size is None:
            size = 200
        return list(islice(self.results, size))

    def fetchall(self):
        """
        Fetch all results from a previously executed query.
        """
        return list(self.results)

    def close(self):
        pass


class Connection(object):
    """
    params:
            connection params ...,
            errorhandler: function with following arguments
                    ``errorhandler(connection, cursor, errorclass, errorvalue)``
            use_introspection: bool
    """
    # close and commit can be safely ignored because everything is
    # committed automatically and REST is stateles. They are
    # unconditionally required by Django 1.6+.

    Error = Error
    InterfaceError = InterfaceError
    DatabaseError = DatabaseError
    DataError = DataError
    OperationalError = OperationalError
    IntegrityError = IntegrityError
    InternalError = InternalError
    ProgrammingError = ProgrammingError
    NotSupportedError = NotSupportedError

    # DB API methods

    def __init__(self, **params):
        self.errorhandler = params.pop('errorhandler', standard_errorhandler)
        self.use_introspection = params.pop('use_introspection', True)
        # ...
        self._connection = True  # ...
        pass

    def close(self):
        self._check()
        self._connection = None
        print("close..")

    def commit(self):
        self._check()

    def rollback(self):
        self._check()
        log.info("Rollback is not implemented.")

    def cursor(self):
        self._check()
        print("cursor ???")
        return Cursor(self)

    # other methods

    def _check(self):
        if not self._connection:
            raise InterfaceError("Connection Closed")

    def err_hand(self, errorclass, errorvalue):
        "call the errorhandler"
        self.errorhandler(self, None, errorclass, errorvalue)

    def put_metadata(self, data):
        """
        Put metadata from models to prefill metadate cache, insted of introspection.
        It is important for:
            relationship names
            Date, Time, Timestamp
        """
        pass


def rest_api_url(sf_session, service, *args):
    """Join the URL of REST_API

    Examples: rest_url(sf_session, "query?q=select+id+from+Organization")
              rest_url(sf_session, "sobject", "Contact", id)
    """
    return '{base}/services/data/v{version}/{service}{slash_args}'.format(
        base=sf_session.auth.instance_url,
        version=salesforce.API_VERSION,
        service=service,
        slash_args=''.join('/' + x for x in args)
    )


# DB API function
def connect(**params):
    return Connection(**params)


# LOW LEVEL


def getaddrinfo_wrapper(host, port, family=socket.AF_INET, socktype=0, proto=0, flags=0):
    """Patched 'getaddrinfo' with default family IPv4 (enabled by settings IPV4_ONLY=True)"""
    return orig_getaddrinfo(host, port, family, socktype, proto, flags)

# fix dep IPV4_ONLY
# patch to IPv4 if required and not patched by anything other yet
if getattr(settings, 'IPV4_ONLY', False) and socket.getaddrinfo.__module__ in ('socket', '_socket'):
    log.info("Patched socket to IPv4 only")
    orig_getaddrinfo = socket.getaddrinfo
    # replace the original socket.getaddrinfo by our version
    socket.getaddrinfo = getaddrinfo_wrapper

# ----


# fix dep SALESFORCE_QUERY_TIMEOUT
def handle_api_exceptions(url, f, *args, **kwargs):
    """Call REST API and handle exceptions
    Params:
        f:  instance method requests.get or requests.post...
        _cursor: sharing the debug information in cursor
    """
    # pdb.set_trace()
    # print("== REQUEST %s | %s | %s | %s" % (url, f, args, kwargs))
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
    if response.status_code == 401 and f.__self__.auth.can_reauthenticate:
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
    verbose = not getattr(getattr(_cursor, 'db', None), 'debug_silent', False)
    # Errors are reported in the body
    if 'json' not in response.headers.get('Content-Type', ''):
        raise OperationalError("HTTP error %d: %s" % (response.status_code, response.text))
    else:
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


def extract_values(query):
    """
    Extract values from insert or update query.
    Supports bulk_create
    """
    if isinstance(query, subqueries.UpdateQuery):
        row = query.values
        return extract_values_inner(row, query)
    else:
        ret = []
        for row in query.objs:
            ret.append(extract_values_inner(row, query))
        return ret


# fix dep subqueries, model...
def extract_values_inner(row, query):
    from salesforce.backend.operations import DefaultedOnCreate
    from salesforce.fields import NOT_UPDATEABLE, NOT_CREATEABLE
    d = dict()
    fields = query.model._meta.fields
    for index in range(len(fields)):
        field = fields[index]
        sf_read_only = getattr(field, 'sf_read_only', 0)
        if (
            field.get_internal_type() == 'AutoField' or
            isinstance(query, subqueries.UpdateQuery) and (sf_read_only & NOT_UPDATEABLE) != 0 or
            isinstance(query, subqueries.InsertQuery) and (sf_read_only & NOT_CREATEABLE) != 0
        ):
            continue
        if(isinstance(query, subqueries.UpdateQuery)):
            # update
            value_or_empty = [value for qfield, model, value in query.values if qfield.name == field.name]
            if value_or_empty:
                [value] = value_or_empty
            else:
                assert len(query.values) < len(fields), \
                    "Match name can miss only with an 'update_fields' argument."
                continue
        else:
            # insert
            value = getattr(row, field.attname)
        # The 'DEFAULT' is a backward compatibility name.
        if isinstance(field, (models.ForeignKey, models.BooleanField, models.DecimalField)):
            if value in ('DEFAULT', 'DEFAULTED_ON_CREATE'):
                continue
        if isinstance(value, DefaultedOnCreate):
            continue
        d[field.column] = arg_to_sf(value)
    return d


def quoted_string_literal(s):
    """
    SOQL requires single quotes to be escaped.
    http://www.salesforce.com/us/developer/docs/soql_sosl/Content/sforce_api_calls_soql_select_quotedstringescapes.htm
    """
    try:
        return "'%s'" % (s.replace("\\", "\\\\").replace("'", "\\'"),)
    except TypeError:
        raise NotImplementedError("Cannot quote %r objects: %r" % (type(s), s))


def str_dict(some_dict):
    """Convert dict of ascii str/unicode to dict of str, if necessary"""
    return {str(k): str(v) for k, v in some_dict.items()}


# fix dep TIME_ZONE
def date_literal(d):
    if not d.tzinfo:
        tz = pytz.timezone(settings.TIME_ZONE)
        d = tz.localize(d, is_dst=time.daylight)
    # Format of `%z` is "+HHMM"
    tzname = datetime.datetime.strftime(d, "%z")
    return datetime.datetime.strftime(d, "%Y-%m-%dT%H:%M:%S.000") + tzname


def sobj_id(obj):
    return obj.pk


# fix dep SalesforceModel
def arg_to_soql(arg):
    """
    Perform necessary SOQL quoting on the arg.
    """
    if(isinstance(arg, models.SalesforceModel)):
        return sql_conversions[models.SalesforceModel](arg)
    if(isinstance(arg, decimal.Decimal)):
        return sql_conversions[decimal.Decimal](arg)
    return sql_conversions.get(type(arg), sql_conversions[str])(arg)


# fix dep SalesforceModel
def arg_to_sf(arg):
    """
    Perform necessary JSON conversion on the arg.
    """
    if(isinstance(arg, models.SalesforceModel)):
        return json_conversions[models.SalesforceModel](arg)
    if(isinstance(arg, decimal.Decimal)):
        return json_conversions[decimal.Decimal](arg)
    return json_conversions.get(type(arg), json_conversions[str])(arg)

# fix dep SalesforceModel
# supported types
json_conversions = {
    int: str,
    float: lambda o: '%.15g' % o,
    type(None): lambda s: None,
    str: lambda o: o,  # default
    bool: lambda s: str(s).lower(),
    datetime.date: lambda d: datetime.date.strftime(d, "%Y-%m-%d"),
    datetime.datetime: date_literal,
    datetime.time: lambda d: datetime.time.strftime(d, "%H:%M:%S.%f"),
    decimal.Decimal: float,
    models.SalesforceModel: sobj_id,
}
if not PY3:
    json_conversions[long] = str

sql_conversions = json_conversions.copy()
sql_conversions.update({
    type(None): lambda s: 'NULL',
    str: quoted_string_literal,  # default
})

if not PY3:
    sql_conversions[unicode] = lambda s: quoted_string_literal(s.encode('utf8'))
    json_conversions[unicode] = lambda s: s.encode('utf8')
