# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Salesforce object query and queryset customizations.
"""
# TODO hynekcer: class CursorWrapper should
#      be moved to salesforce.backend.driver at the next big refactoring
#      (Evenso some low level internals of salesforce.auth should be moved to
#      salesforce.backend.driver.Connection)

from __future__ import print_function
import datetime
import decimal
import logging
import pytz
from itertools import islice

from django.conf import settings
from django.core.serializers import python
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.db.models import query, Count
from django.db.models.sql import Query, RawQuery, constants, subqueries
from django.db.models.sql.datastructures import EmptyResultSet
from django.utils.six import PY3

from salesforce import models, DJANGO_18_PLUS, DJANGO_110_PLUS
from salesforce.backend.driver import DatabaseError, SalesforceError, handle_api_exceptions, API_STUB
from salesforce.backend.compiler import SQLCompiler
from salesforce.backend.operations import DefaultedOnCreate
from salesforce.fields import NOT_UPDATEABLE, NOT_CREATEABLE, SF_PK
import salesforce.backend.driver

if not DJANGO_110_PLUS:
    from django.db.models.query_utils import deferred_class_factory

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode
try:
    import json
except ImportError:
    import simplejson as json

log = logging.getLogger(__name__)


# Values of seconds are with 3 decimal places in SF, but they are rounded to
# whole seconds for the most of fields.
SALESFORCE_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f+0000'
DJANGO_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f-00:00'



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


def quoted_string_literal(s, d):
    """
    SOQL requires single quotes to be escaped.
    http://www.salesforce.com/us/developer/docs/soql_sosl/Content/sforce_api_calls_soql_select_quotedstringescapes.htm
    """
    try:
        return "'%s'" % (s.replace("\\", "\\\\").replace("'", "\\'"),)
    except TypeError as e:
        raise NotImplementedError("Cannot quote %r objects: %r" % (type(s), s))

def process_args(args):
    """
    Perform necessary quoting on the arg list.
    """
    def _escape(item, conv):
        if(isinstance(item, models.SalesforceModel)):
            return conv.get(models.SalesforceModel, conv[str])(item, conv)
        if(isinstance(item, decimal.Decimal)):
            return conv.get(decimal.Decimal, conv[str])(item, conv)
        return conv.get(type(item), conv[str])(item, conv)
    return tuple([_escape(x, sql_conversions) for x in args])

def process_json_args(args):
    """
    Perform necessary JSON quoting on the arg list.
    """
    def _escape(item, conv):
        if(isinstance(item, models.SalesforceModel)):
            return conv.get(models.SalesforceModel, conv[str])(item, conv)
        if(isinstance(item, decimal.Decimal)):
            return conv.get(decimal.Decimal, conv[str])(item, conv)
        return conv.get(type(item), conv[str])(item, conv)
    return tuple([_escape(x, json_conversions) for x in args])


def prep_for_deserialize_inner(model, record, init_list=None):
    fields = dict()
    for x in model._meta.fields:
        if not x.primary_key and (not init_list or x.name in init_list):
            if x.column.endswith('.Type'):
                # Type of generic foreign key
                simple_column, _ = x.column.split('.')
                fields[x.name] = record[simple_column]['Type']
            else:
                # Normal fields
                field_val = record[x.column]
                #db_type = x.db_type(connection=connections[using])
                if(x.__class__.__name__ == 'DateTimeField' and field_val is not None):
                    d = datetime.datetime.strptime(field_val, SALESFORCE_DATETIME_FORMAT)
                    import pytz
                    d = d.replace(tzinfo=pytz.utc)
                    if settings.USE_TZ:
                        fields[x.name] = d.strftime(DJANGO_DATETIME_FORMAT)
                    else:
                        tz = pytz.timezone(settings.TIME_ZONE)
                        d = tz.normalize(d.astimezone(tz))
                        fields[x.name] = d.strftime(DJANGO_DATETIME_FORMAT[:-6])
                else:
                    fields[x.name] = field_val
    return fields

def prep_for_deserialize(model, record, using, init_list=None):
    """
    Convert a record from SFDC (decoded JSON) to dict(model string, pk, fields)
    If fixes fields of some types. If names of required fields `init_list `are
    specified, then only these fields are processed.
    """
    from salesforce.backend import base
    # TODO the parameter 'using' is not currently important.
    attribs = record.pop('attributes')

    mod = model.__module__.split('.')
    if(mod[-1] == 'models'):
        app_label = mod[-2]
    elif(hasattr(model._meta, 'app_label')):
        app_label = getattr(model._meta, 'app_label')
    else:
        raise ImproperlyConfigured("Can't discover the app_label for %s, you must specify it via model meta options.")

    if len(record.keys()) == 1 and model._meta.db_table in record:
        # this is for objects with ManyToManyField and OneToOneField
        while len(record) == 1:
            record = list(record.values())[0]
            if record is None:
                return None

    fields = prep_for_deserialize_inner(model, record, init_list=init_list)

    if init_list and set(init_list).difference(fields).difference([SF_PK]):
        raise DatabaseError("Not found some expected fields")

    return dict(
        model='.'.join([app_label, model.__name__]),
        pk=record.pop('Id'),
        fields=fields,
    )


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


def extract_values_inner(row, query):
    d = dict()
    fields = query.model._meta.fields
    for index in range(len(fields)):
        field = fields[index]
        if (field.get_internal_type() == 'AutoField' or
                isinstance(query, subqueries.UpdateQuery) and (getattr(field, 'sf_read_only', 0) & NOT_UPDATEABLE) != 0 or
                isinstance(query, subqueries.InsertQuery) and (getattr(field, 'sf_read_only', 0) & NOT_CREATEABLE) != 0):
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
        [arg] = process_json_args([value])
        d[field.column] = arg
    return d


class SalesforceRawQuerySet(query.RawQuerySet):
    def __len__(self):
        if self.query.cursor is None:
            # force the query
            self.query.get_columns()
        return self.query.cursor.rowcount

class SalesforceQuerySet(query.QuerySet):
    """
    Use a custom SQL compiler to generate SOQL-compliant queries.
    """
    def iterator(self):
        """
        An iterator over the results from applying this QuerySet to the
        remote web service.
        """
        try:
            sql, params = SQLCompiler(self.query, connections[self.db], None).as_sql()
        except EmptyResultSet:
            raise StopIteration
        cursor = CursorWrapper(connections[self.db], self.query)
        cursor.execute(sql, params)

        only_load = self.query.get_loaded_field_names()
        load_fields = []
        # If only/defer clauses have been specified,
        # build the list of fields that are to be loaded.
        if not only_load:
            model_cls = self.model
            init_list = None
        else:
            fields = self.model._meta.concrete_fields
            for field in fields:
                model = field.model._meta.concrete_model
                if model is None:
                    model = self.model
                try:
                    selected_name = field.attname if DJANGO_18_PLUS else field.name
                    if selected_name in only_load[model]:
                        # Add a field that has been explicitly included
                        load_fields.append(field.name)
                except KeyError:
                    # Model wasn't explicitly listed in the only_load table
                    # Therefore, we need to load all fields from this model
                    load_fields.append(field.name)

            init_list = []
            skip = set()
            for field in fields:
                if field.name not in load_fields:
                    skip.add(field.attname)
                else:
                    init_list.append(field.name)
            if DJANGO_110_PLUS:
                model_cls = self.model
            else:
                model_cls = deferred_class_factory(self.model, skip)

        field_names = self.query.get_loaded_field_names()
        for res in python.Deserializer(
                x for x in
                (prep_for_deserialize(model_cls, r, self.db, init_list)
                 for r in cursor.results
                 )
                if x is not None
        ):
            # Store the source database of the object
            res.object._state.db = self.db
            # This object came from the database; it's not being added.
            res.object._state.adding = False

            if DJANGO_110_PLUS and init_list is not None and len(init_list) != len(model_cls._meta.concrete_fields):
                raise NotImplementedError("methods defer() and only() are not implemented for Django 1.10 yet")

            yield res.object

    def query_all(self):
        """
        Allows querying for also deleted or merged records.
            Lead.objects.query_all().filter(IsDeleted=True,...)
        https://www.salesforce.com/us/developer/docs/api_rest/Content/resources_queryall.htm
        """
        obj = self._clone(klass=SalesforceQuerySet)
        obj.query.set_query_all()
        return obj

class SalesforceRawQuery(RawQuery):
    def clone(self, using):
        return SalesforceRawQuery(self.sql, using, params=self.params)

    def get_columns(self):
        if self.cursor is None:
            self._execute_query()
        converter = connections[self.using].introspection.table_name_converter
        if self.cursor.rowcount > 0:
            return [converter(col) for col in self.cursor.first_row.keys() if col != 'attributes']
        # TODO hy: A more general fix is desirable with rewriting more code.
        #   This is changed due to Django 1.8.4+  https://github.com/django/django/pull/5036
        #   related to https://code.djangoproject.com/ticket/12768
        return ['Id'] if DJANGO_18_PLUS else [SF_PK]

    def _execute_query(self):
        self.cursor = CursorWrapper(connections[self.using], self)
        self.cursor.execute(self.sql, self.params)

    def __repr__(self):
        return "<SalesforceRawQuery: %s; %r>" % (self.sql, tuple(self.params))

    def __iter__(self):
        #import pdb; pdb.set_trace()
        for row in super(SalesforceRawQuery, self).__iter__():
            if DJANGO_18_PLUS:
                row = [row[k] for k in self.get_columns()]
            yield row


class SalesforceQuery(Query):
    """
    Override aggregates.
    """
    # Warn against name collision: The name 'aggregates' is the name of
    # a new property introduced by Django 1.7 to the parent class
    # 'django.db.models.sql.query.Query'.
    # 'aggregates_module' is overriden here, to be visible in the base class.
    from salesforce.backend import aggregates as aggregates_module

    def __init__(self, *args, **kwargs):
        super(SalesforceQuery, self).__init__(*args, **kwargs)
        self.is_query_all = False
        self.first_chunk_len = None
        self.max_depth = 1

    def clone(self, klass=None, memo=None, **kwargs):
        query = Query.clone(self, klass, memo, **kwargs)
        query.is_query_all = self.is_query_all
        return query

    def has_results(self, using):
        q = self.clone()
        compiler = q.get_compiler(using=using)
        return bool(compiler.execute_sql(constants.SINGLE))

    def set_query_all(self):
        self.is_query_all = True

    if DJANGO_18_PLUS:
        def get_count(self, using):
            """
            Performs a COUNT() query using the current filter constraints.
            """
            obj = self.clone()
            obj.add_annotation(Count('pk'), alias='x_sf_count', is_summary=True)
            number = obj.get_aggregation(using, ['x_sf_count'])['x_sf_count']
            if number is None:
                number = 0
            return number


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
        if salesforce.backend.driver.beatbox is None:
            self.use_soap_for_bulk = False

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    @property
    def oauth(self):
        return self.session.auth.get_auth()

    def execute(self, q, args=()):
        """
        Send a query to the Salesforce API.
        """
        self.rowcount = None
        if isinstance(self.query, SalesforceQuery) or self.query is None:
            response = self.execute_select(q, args)
            #print("response : %s" % response.text)
        elif isinstance(self.query, SalesforceRawQuery):
            response = self.execute_select(q, args)
        elif isinstance(self.query, subqueries.InsertQuery):
            response = self.execute_insert(self.query)
        elif isinstance(self.query, subqueries.UpdateQuery):
            response = self.execute_update(self.query)
        elif isinstance(self.query, subqueries.DeleteQuery):
            response = self.execute_delete(self.query)
        else:
            raise DatabaseError("Unsupported query: type %s: %s" % (type(self.query), self.query))

        if response and isinstance(response, list):
            # bulk operation SOAP
            if all(x['success'] for x in response):
                self.lastrowid = [item['id'] for item in response]
        # the encoding is detected automatically, e.g. from headers
        elif(response and response.text):
            # parse_float set to decimal.Decimal to avoid precision errors when
            # converting from the json number to a float to a Decimal object
            # on a model's DecimalField...converts from json number directly
            # a Decimal object
            data = response.json(parse_float=decimal.Decimal)
            # a SELECT query
            if('totalSize' in data):
                self.rowcount = data['totalSize']
            # a successful INSERT query, return after getting PK
            elif('success' in data and 'id' in data):
                self.lastrowid = data['id']
                return
            elif data['hasErrors'] == False:
                # save id from bulk_create even if Django don't use it
                if data['results'] and data['results'][0]['result']:
                    self.lastrowid = [item['result']['id'] for item in data['results']]
                return
            # something we don't recognize
            else:
                raise DatabaseError(data)

            if q.upper().startswith('SELECT COUNT() FROM'):
                # COUNT() queries in SOQL are a special case, as they don't actually return rows
                self.results = iter([[self.rowcount]])
            else:
                if self.query:
                    self.query.first_chunk_len = len(data['records'])
                self.first_row = data['records'][0] if data['records'] else None
                self.results = self.query_results(data)
        else:
            self.results = iter([])

    def execute_select(self, q, args):
        processed_sql = str(q) % process_args(args)
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
        if isinstance(pk, (tuple, list, SalesforceQuerySet)):
            if not self.use_soap_for_bulk:
                # bulk by REST
                url = rest_api_url(self.session, 'composite/batch')
                last_mod = None
                if pk and hasattr(pk[0], 'pk'):
                    last_mod = max(getattr(x, fld.name)
                                   for x in pk if hasattr(x, 'pk')
                                   for fld in x._meta.fields if fld.db_column=='LastModifiedDate'
                                   )
                if last_mod is None:
                    last_mod = datetime.datetime.utcnow()
                post_data = {
                    'batchRequests': [{'method' : 'PATCH',
                                       'url' : 'v{0}/sobjects/{1}/{2}'.format(salesforce.API_VERSION,
                                                                              table,
                                                                              getattr(x, 'pk', x)),
                                       'richInput': post_data
                                       }
                                      for x in pk
                                      ]
                             }
                import time
                headers.update({'If-Unmodified-Since': time.strftime('%a, %d %b %Y %H:%M:%S GMT',
                               (last_mod + datetime.timedelta(seconds=0)).timetuple())})
                _ret = handle_api_exceptions(url, self.session.post, headers=headers, data=json.dumps(post_data), _cursor=self)
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
            _ret = handle_api_exceptions(url, self.session.patch, headers=headers, data=json.dumps(post_data), _cursor=self)
        self.rowcount = 1
        return _ret

    def execute_delete(self, query):
        table = query.model._meta.db_table
        ## the root where node's children may itself have children..
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
            url =  self.oauth['id']
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
                ANNOTATION_SELECT_NAME = 'annotation_select' if DJANGO_18_PLUS else 'aggregate_select'
                if rec['attributes']['type'] == 'AggregateResult' and hasattr(self.query, ANNOTATION_SELECT_NAME):
                    annotation_select = getattr(self.query, ANNOTATION_SELECT_NAME)
                    assert len(rec) -1 == len(list(annotation_select.items()))
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


def str_dict(some_dict):
    """Convert dict of ascii str/unicode to dict of str, if necessary"""
    return {str(k): str(v) for k, v in some_dict.items()}


string_literal = quoted_string_literal
def date_literal(d, c):
    if not d.tzinfo:
        import time
        tz = pytz.timezone(settings.TIME_ZONE)
        d = tz.localize(d, is_dst=time.daylight)
    # Format of `%z` is "+HHMM"
    tzname = datetime.datetime.strftime(d, "%z")
    return datetime.datetime.strftime(d, "%Y-%m-%dT%H:%M:%S.000") + tzname

def sobj_id(obj, conv):
    return obj.pk

# supported types
sql_conversions = {
    int: lambda s,d: str(s),
    float: lambda o,d: '%.15g' % o,
    type(None): lambda s,d: 'NULL',
    str: lambda o,d: string_literal(o, d), # default
    bool: lambda s,d: str(s).lower(),
    datetime.date: lambda d,c: datetime.date.strftime(d, "%Y-%m-%d"),
    datetime.datetime: lambda d,c: date_literal(d, c),
    decimal.Decimal: lambda s,d: float(s),
    models.SalesforceModel: sobj_id,
}
if not PY3:
    sql_conversions[long] = lambda s,d: str(s)
    sql_conversions[unicode] = lambda s,d: string_literal(s.encode('utf8'), d)

# supported types
json_conversions = {
    int: lambda s,d: str(s),
    float: lambda o,d: '%.15g' % o,
    type(None): lambda s,d: None,
    str: lambda o,d: o, # default
    bool: lambda s,d: str(s).lower(),
    datetime.date: lambda d,c: datetime.date.strftime(d, "%Y-%m-%d"),
    datetime.datetime: date_literal,
    datetime.time: lambda d,c: datetime.time.strftime(d, "%H:%M:%S.%f"),
    decimal.Decimal: lambda s,d: float(s),
    models.SalesforceModel: sobj_id,
}
if not PY3:
    json_conversions[long] = lambda s,d: str(s)
    json_conversions[unicode] = lambda s,d: s.encode('utf8')
