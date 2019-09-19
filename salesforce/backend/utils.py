"""
CursorWrapper (like django.db.backends.utils)
"""
import datetime
import decimal
import logging

import pytz
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models, NotSupportedError
from django.db.models.sql import subqueries, Query, RawQuery
from six import text_type

import salesforce
from salesforce.backend import DJANGO_111_PLUS
from salesforce.backend.operations import DefaultedOnCreate
from salesforce.dbapi.driver import (
    DatabaseError, merge_dict,
    register_conversion, arg_to_json, SALESFORCE_DATETIME_FORMAT)
from salesforce.fields import NOT_UPDATEABLE, NOT_CREATEABLE, SF_PK

log = logging.getLogger(__name__)

# pylint:disable=invalid-name

DJANGO_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S.%f-00:00'

MIGRATIONS_QUERY_TO_BE_IGNORED = "SELECT django_migrations.app, django_migrations.name FROM django_migrations"


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
                # db_type = x.db_type(connection=connections[using])
                if x.__class__.__name__ == 'DateTimeField' and field_val is not None:
                    d = datetime.datetime.strptime(field_val, SALESFORCE_DATETIME_FORMAT)
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


def prep_for_deserialize(model, record, using, init_list=None):  # pylint:disable=unused-argument
    """
    Convert a record from SFDC (decoded JSON) to dict(model string, pk, fields)
    If fixes fields of some types. If names of required fields `init_list `are
    specified, then only these fields are processed.
    """
    # TODO the parameter 'using' is not currently important.
    attribs = record.pop('attributes')  # NOQA pylint:disable=unused-variable

    mod = model.__module__.split('.')
    if hasattr(model._meta, 'app_label'):
        app_label = getattr(model._meta, 'app_label')
    elif mod[-1] == 'models':
        app_label = mod[-2]
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
    # pylint
    if isinstance(query, subqueries.UpdateQuery):
        row = query.values
        return extract_values_inner(row, query)
    if isinstance(query, subqueries.InsertQuery):
        ret = []
        for row in query.objs:
            ret.append(extract_values_inner(row, query))
        return ret
    raise NotSupportedError


def extract_values_inner(row, query):
    d = dict()
    fields = query.model._meta.fields
    for _, field in enumerate(fields):
        sf_read_only = getattr(field, 'sf_read_only', 0)
        if (field.get_internal_type() == 'AutoField' or
                isinstance(query, subqueries.UpdateQuery) and (sf_read_only & NOT_UPDATEABLE) != 0 or
                isinstance(query, subqueries.InsertQuery) and (sf_read_only & NOT_CREATEABLE) != 0):
            continue
        if isinstance(query, subqueries.UpdateQuery):
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
        d[field.column] = arg_to_json(value)
    return d


class CursorWrapper(object):
    """
    A wrapper that emulates the behavior of a database cursor.

    This is the class that is actually responsible for making connections
    to the SF REST API
    """

    # pylint:disable=too-many-instance-attributes,too-many-public-methods
    def __init__(self, db):
        """
        Connect to the Salesforce API.
        """
        self.db = db
        self.query = None
        self.session = db.sf_session
        self.rowcount = None
        self.first_row = None
        self.lastrowid = None  # not moved to driver because INSERT is implemented here
        self.cursor = self.db.connection.cursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    @property
    def oauth(self):
        return self.session.auth.get_auth()

    def execute(self, q, args=()):
        """
        Send a query to the Salesforce API.
        """
        # pylint:disable=too-many-branches
        self.rowcount = None
        response = None
        if self.query is None:
            self.execute_select(q, args)
        else:
            response = self.execute_django(q, args)
            if isinstance(response, list):
                return

        # the encoding is detected automatically, e.g. from headers
        if response and response.text:
            # parse_float set to decimal.Decimal to avoid precision errors when
            # converting from the json number to a float and then to a Decimal object
            # on a model's DecimalField. This converts from json number directly
            # to a Decimal object
            data = response.json(parse_float=decimal.Decimal)
            # a SELECT query
            if 'totalSize' in data:
                # SELECT
                self.rowcount = data['totalSize']
            # a successful INSERT query, return after getting PK
            elif 'success' in data and 'id' in data:
                self.lastrowid = data['id']
                return
            elif 'compositeResponse' in data:
                # TODO treat error reporting for composite requests
                self.lastrowid = [x['body']['id'] if x['body'] is not None else x['referenceId']
                                  for x in data['compositeResponse']]
                return
            elif data['hasErrors'] is False:
                # it is from Composite Batch request
                # save id from bulk_create even if Django don't use it
                if data['results'] and data['results'][0]['result']:
                    self.lastrowid = [item['result']['id'] for item in data['results']]
                return
            # something we don't recognize
            else:
                raise DatabaseError(data)

            if not q.upper().startswith('SELECT COUNT() FROM'):
                self.first_row = data['records'][0] if data['records'] else None

    def prepare_query(self, query):
        self.query = query

    def execute_django(self, soql, args=()):
        """
        Fixed execute for queries coming from Django query compilers
        """
        response = None
        sqltype = soql.split(None, 1)[0].upper()
        if isinstance(self.query, subqueries.InsertQuery):
            response = self.execute_insert(self.query)
        elif isinstance(self.query, subqueries.UpdateQuery):
            response = self.execute_update(self.query)
        elif isinstance(self.query, subqueries.DeleteQuery):
            response = self.execute_delete(self.query)
        elif isinstance(self.query, RawQuery):
            self.execute_select(soql, args)
        elif sqltype in ('SAVEPOINT', 'ROLLBACK', 'RELEASE'):
            log.info("Ignored SQL command '%s'", sqltype)
            return
        elif isinstance(self.query, Query):
            self.execute_select(soql, args)
        else:
            raise DatabaseError("Unsupported query: type %s: %s" % (type(self.query), self.query))
        return response

    def execute_select(self, soql, args):
        if soql != MIGRATIONS_QUERY_TO_BE_IGNORED:
            # normal query
            is_query_all = self.query and self.query.is_query_all
            self.cursor.execute(soql, args, query_all=is_query_all)
        else:
            # Nothing queried about django_migrations to SFDC and immediately responded that
            # nothing about migration status is recorded in SFDC.
            #
            # That is required by "makemigrations" to accept this query.
            # Empty results are possible.
            # (It could be eventually replaced by: "SELECT app__c, Name FROM django_migrations__c")
            self.cursor._iter = iter([])  # pylint:disable=protected-access
            self.cursor.rowcount = 0
        self.rowcount = self.cursor.rowcount

    def query_more(self, nextRecordsUrl):
        return self.handle_api_exceptions('GET', nextRecordsUrl)

    def execute_insert(self, query):
        table = query.model._meta.db_table
        if table == 'django_migrations':
            return
        post_data = extract_values(query)
        obj_url = self.db.connection.rest_api_url('sobjects', table, relative=True)
        if len(post_data) == 1:
            # single object
            post_data = post_data[0]
            return self.handle_api_exceptions('POST', obj_url, json=post_data)
        if self.db.connection.composite_type == 'sobject-collections':
            # SObject Collections
            records = [merge_dict(x, type_=table) for x in post_data]
            ret = self.db.connection.sobject_collections_request('POST', records)
            self.lastrowid = ret
            self.rowcount = len(ret)
            return
        # composite by REST
        composite_data = [{'method': 'POST', 'url': obj_url, 'referenceId': str(i), 'body': row}
                          for i, row in enumerate(post_data)]
        ret = self.db.connection.composite_request(composite_data)
        return ret

    def get_pks_from_query(self, query):
        """Prepare primary keys for update and delete queries"""
        where = query.where
        sql = None
        if where.connector == 'AND' and not where.negated and len(where.children) == 1:
            # simple cases are optimized, especially because a suboptimal
            # nested query based on the same table is not allowed by SF
            child = where.children[0]
            if (child.lookup_name in ('exact', 'in') and child.lhs.target.column == 'Id'
                    and not child.bilateral_transforms and child.lhs.target.model is self.query.model):
                pks = child.rhs
                if child.lookup_name == 'exact':
                    assert isinstance(pks, text_type)
                    return [pks]
                # lookup_name 'in'
                assert not child.bilateral_transforms
                if isinstance(pks, (tuple, list)):
                    return pks
                if DJANGO_111_PLUS:
                    assert isinstance(pks, Query) and type(pks).__name__ == 'SalesforceQuery'
                    # # alternative solution:
                    # return list(salesforce.backend.query.SalesforceQuerySet(pk.model, query=pk, using=pk._db))

                    sql, params = pks.get_compiler('salesforce').as_sql()
                else:
                    assert isinstance(pks, salesforce.backend.query.SalesforceQuerySet)
                    return [x.pk for x in pks]
        if not sql:
            # a subquery is necessary in this case
            where_sql, params = where.as_sql(query.get_compiler('salesforce'), self.db.connection)
            sql = "SELECT Id FROM {} WHERE {}".format(query.model._meta.db_table, where_sql)
        with self.db.cursor() as cur:
            cur.execute(sql, params)
            assert len(cur.description) == 1 and cur.description[0][0] == 'Id'
            return [x[0] for x in cur]

    def execute_update(self, query):
        table = query.model._meta.db_table
        post_data = extract_values(query)
        pks = self.get_pks_from_query(query)
        log.debug('UPDATE %s(%s)%r', table, pks, post_data)
        if not pks:
            return
        obj_url = self.db.connection.rest_api_url('sobjects', table, '', relative=True)
        if len(pks) == 1:
            # single request
            ret = self.handle_api_exceptions('PATCH', obj_url + pks[0], json=post_data)
            self.rowcount = 1
            return ret
        if self.db.connection.composite_type == 'sobject-collections':
            # SObject Collections
            records = [merge_dict(post_data, id=pk, type_=table) for pk in pks]
            ret = self.db.connection.sobject_collections_request('PATCH', records)
            self.lastrowid = ret
            self.rowcount = len(ret)
            return
        # composite by REST
        composite_data = [{'method': 'PATCH', 'url': obj_url + pk, 'referenceId': pk, 'body': post_data}
                          for pk in pks]
        ret = self.db.connection.composite_request(composite_data)
        self.rowcount = len([x for x in ret.json()['compositeResponse'] if x['httpStatusCode'] == 204])
        return ret

    def execute_delete(self, query):
        table = query.model._meta.db_table
        pks = self.get_pks_from_query(query)

        log.debug('DELETE %s(%s)', table, pks)
        if not pks:
            self.rowcount = 0
            return
        if len(pks) == 1:
            ret = self.handle_api_exceptions('DELETE', 'sobjects', table, pks[0])
            self.rowcount = 1 if (ret and ret.status_code == 204) else 0
            return ret
        if self.db.connection.composite_type == 'sobject-collections':
            # SObject Collections
            records = pks
            ret = self.db.connection.sobject_collections_request('DELETE', records)
            self.lastrowid = ret
            self.rowcount = len(ret)
            return
        # bulk by REST
        url = self.db.connection.rest_api_url('sobjects', table, '', relative=True)
        composite_data = [{'method': 'DELETE', 'url': url + pk, 'referenceId': pk}
                          for pk in pks]
        ret = self.db.connection.composite_request(composite_data)
        self.rowcount = len([x for x in ret.json()['compositeResponse'] if x['httpStatusCode'] == 204])

    # The following 3 methods (execute_ping, id_request, versions_request)
    # can be renamed soon or moved.

    def urls_request(self):
        """Empty REST API request is useful after long inactivity before POST.

        It ensures that the token will remain valid for at least half life time
        of the new token. Otherwise it would be an awkward doubt if a timeout on
        a lost connection is possible together with token expire in a post
        request (insert).
        """
        ret = self.handle_api_exceptions('GET', '')
        return str_dict(ret.json())

    def id_request(self):
        """The Force.com Identity Service (return type dict of text_type)"""
        # https://developer.salesforce.com/page/Digging_Deeper_into_OAuth_2.0_at_Salesforce.com?language=en&language=en#The_Force.com_Identity_Service

        if 'id' in self.oauth:
            url = self.oauth['id']
        else:
            # dynamic auth without 'id' parameter
            url = self.urls_request()['identity']
        ret = self.handle_api_exceptions('GET', url)  # TODO
        return ret.json()

    def versions_request(self):
        """List Available REST API Versions"""
        ret = self.handle_api_exceptions('GET', '', api_ver='')
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
        return self.cursor

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchmany(self, size=None):
        return self.cursor.fetchmany(size=size)

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def description(self):
        return self.cursor.description

    def close(self):
        self.cursor.close()

    def commit(self):
        self.cursor.commit()

    def rollback(self):
        self.cursor.rollback()

    def handle_api_exceptions(self, method, *url_parts, **kwargs):
        return self.cursor.handle_api_exceptions(method, *url_parts, **kwargs)


def str_dict(some_dict):
    """Convert dict of ascii str/unicode to dict of str, if necessary"""
    return {str(k): str(v) for k, v in some_dict.items()}


def sobj_id(obj):
    assert obj._salesforce_object  # pylint:disable=protected-access
    return obj.pk


register_conversion(models.Model, json_conv=sobj_id, subclass=True)
