"""
Minimal code to support ignored makemigrations  (like django.db.backends.*.schema)

without interaction to SF (without migrate)
"""
from typing import Any, Callable, Dict, List, Type, Union
import logging
import random
import re
import time

import requests
from django.db import NotSupportedError
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.backends.ddl_references import Statement
from django.db.models import Field, ForeignKey, Model, NOT_PROVIDED, PROTECT
from salesforce.dbapi.exceptions import IntegrityError, OperationalError, SalesforceError
from salesforce import defaults

log = logging.getLogger(__name__)

# source: https://gist.github.com/wadewegner/9139536
METADATA_ENVELOPE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:apex="http://soap.sforce.com/2006/08/apex"
                  xmlns:tns="http://soap.sforce.com/2006/04/metadata"
                  xmlns="http://soap.sforce.com/2006/04/metadata"
                  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Header>
    <tns:SessionHeader>
      <tns:sessionId>{session_id}</tns:sessionId>
    </tns:SessionHeader>
  </soapenv:Header>
  <soapenv:Body>
{body}
  </soapenv:Body>
</soapenv:Envelope>
"""

CREATE_OBJECT_BODY = """
    <tns:createMetadata>
      <metadata xsi:type="CustomObject">
{body}
      </metadata>
    </tns:createMetadata>
"""

UPDATE_OBJECT_BODY = """
    <tns:updateMetadata xmlns="http://soap.sforce.com/2006/04/metadata">
      <tns:metadata xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="tns:CustomObject">
{body}
      </tns:metadata>
    </tns:updateMetadata>
"""

DELETE_METADATA_BODY = """
    <tns:deleteMetadata>
      <tns:type>{metadata_type}</tns:type>
      <tns:fullNames>{custom_object_name}</tns:fullNames>
    </tns:deleteMetadata>
"""

T_PY2XML = Union[str, int, float, Dict[str, Union['T_PY2XML', List['T_PY2XML']]]]  # type: ignore[misc] # recursive


def to_xml(data: T_PY2XML, indent: int = 0) -> str:
    """Format a simple XML body for SOAP API from data very similar to REST API

    Examples are in: salesforce.tests.test_unit.ToXml
    """
    INDENT = 2  # indent step
    if isinstance(data, str):
        return data.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    elif isinstance(data, (int, float)):
        return str(data)
    elif isinstance(data, dict):
        out = []  # type: List[str]
        for tag, val in data.items():
            assert re.match(r'[A-Za-z][0-9A-Za-z_:]*$', tag)
            if not isinstance(val, list):
                val = [val]
            for item in val:
                v_str = to_xml(item, indent + 1)
                wrap_start = '\n' if v_str.endswith('>') else ''
                wrap_end = '\n' + indent * INDENT * ' ' if v_str.endswith('>') else ''
                out.append(indent * INDENT * ' ' + '<{tag}>{wrap_start}{v_str}{wrap_end}</{tag}>'
                           .format(tag=tag, v_str=v_str, wrap_start=wrap_start, wrap_end=wrap_end))
        return '\n'.join(out)
    else:
        raise NotImplementedError("Not implemented conversion from type {} to xml".format(type(data)))


def wrap_debug(func: Callable[..., None]) -> Callable[..., None]:
    def wrapped(self, model: Type[Model], *args: Any, **kwargs: Any) -> None:
        skip = False
        interactive = self.connection.migrate_options.get('ask')
        interact_destructive_production = self.is_production and getattr(func, 'no_destructive_production', False)
        if not interactive and not interact_destructive_production:
            return func(self, model, *args, **kwargs)

        params = ['<model {}>'.format(model._meta.object_name)]
        params.extend([repr(x) for x in args])
        params.extend(['{}={}'.format(k, v) for k, v in kwargs.items()])

        print('\n{}({})'.format(func.__name__, ', '.join(params)))
        answer = input('Run this command [Y/n]:')
        skip = answer.upper() not in ['Y', '']
        if skip:
            return None
        if not interactive:
            return func(self, model, *args, **kwargs)

        try:
            return func(self, model, *args, **kwargs)
        except SalesforceError as exc:
            print(exc)
            answer = input('Stop after this error? [S(stop) / c(continue) / d(debug)]:').upper()
            if answer == 'C':  # continue
                return None
            elif answer == 'D':  # debug
                import pdb; pdb.set_trace()  # noqa
                return None
            raise

    return wrapped


def no_destructive_production(func: Callable[..., None]) -> Callable[..., None]:
    setattr(func, 'no_destructive_production', True)
    return func


class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):
    # pylint:disable=abstract-method  # undefined: prepare_default, quote_value

    DISPLAY_FORMAT = 'A-{0}'

    def __init__(self, connection, collect_sql=False, atomic=True):
        self.conn = connection.connection
        self.connection = connection.connection
        self.collect_sql = collect_sql
        # if self.collect_sql:
        #    self.collected_sql = []
        log.debug('DatabaseSchemaEditor __init__')
        self.cur = self.conn.cursor()
        self.request = self.conn.handle_api_exceptions
        self._permission_set_id = None  # Optional[str]
        self._is_production = None  # Optional[bool];
        self.permission_set_id  # require the permission set
        super().__init__(connection, collect_sql=collect_sql, atomic=atomic)

    # State-managing methods

    def __enter__(self):
        log.debug('DatabaseSchemaEditor __enter__')
        self.deferred_sql = []  # pylint:disable=attribute-defined-outside-init
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        log.debug('DatabaseSchemaEditor __exit__')
        if exc_type is None:
            for sql in self.deferred_sql:
                self.execute(sql)

    @wrap_debug
    def create_model(self, model: Type[Model]) -> None:
        if model._meta.db_table == 'django_migrations':
            model._meta.db_table += '__c'
        db_table = model._meta.db_table
        sf_managed_model = getattr(model._meta.auto_field, 'sf_managed_model', False)
        if sf_managed_model or model._meta.db_table == 'django_migrations__c':
            # TODO if self.connection.migrate_options['batch']:  create also fields by the same request
            body = CREATE_OBJECT_BODY.format(body=to_xml(self.make_model_metadata(model), indent=4))
            response_text = self.metadata_command(action='create', body=body)
            # <?xml version="1.0" encoding="UTF-8"?>
            # <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
            #                   xmlns="http://soap.sforce.com/2006/04/metadata">
            #   <soapenv:Body>
            #     <createResponse>
            #       <result>
            #         <done>false</done>
            #         <id>04sM0000001l43CIAQ</id>
            #         <state>InProgress</state>
            #       </result>
            #     </createResponse>
            #   </soapenv:Body>
            # </soapenv:Envelope>
            entity_id = self.wait_for_entity(db_table, '')

            object_permissions_data = dict(
                # selection by `db_table` was not reliable if the same object is in the trash
                SobjectType=entity_id,
                ParentId=self.permission_set_id,
                PermissionsViewAllRecords=True,
                PermissionsModifyAllRecords=True,
                PermissionsRead=True,
                PermissionsEdit=True,
                PermissionsCreate=True,
                PermissionsDelete=True,
            )
            ret = self.request('POST', 'sobjects/ObjectPermissions', json=object_permissions_data)
            assert ret.status_code == 201

        for field in model._meta.fields:
            sf_managed_field = (getattr(field, 'sf_managed', False) or db_table == 'django_migrations__c'
                                and field.column.lower() != 'id')
            if sf_managed_field:
                if db_table == 'django_migrations__c':
                    field.column += '__c'
                self.add_field(model, field)

    @wrap_debug
    @no_destructive_production
    def delete_model(self, model: Type[Model]) -> None:
        if model._meta.db_table == 'django_migrations':
            model._meta.db_table += '__c'
        sf_managed_model = getattr(model._meta.auto_field, 'sf_managed_model', False)
        if sf_managed_model or model._meta.db_table == 'django_migrations__c':
            log.debug("delete_model %s", model)
            self.check_permissions(model)
            for field in model._meta.fields:
                if isinstance(field, ForeignKey) and getattr(field, 'sf_managed', False):
                    # prevent a duplicit related_name for more deleted copies
                    related_name_orig = field.remote_field.get_accessor_name()  # type: ignore[attr-defined]
                    for retry in range(10):
                        del_suffix = '_del_{:04}'.format(random.randint(0, 9999))
                        field.remote_field.related_name = related_name_orig + del_suffix  # type: ignore[attr-defined]
                        try:
                            self._alter_field(model, field, field)
                            break
                        except SalesforceError as exc:
                            if not ('DUPLICATE_DEVELOPER_NAME' in str(exc) and 'Child Relationship' in str(exc)):
                                raise
            self.delete_metadata('CustomObject', model._meta.db_table)
        else:
            for field in model._meta.fields:
                sf_managed_field = getattr(field, 'sf_managed', False)
                if sf_managed_field:
                    self.remove_field(model, field)

    @wrap_debug
    def alter_db_table(self, model: Type[Model], old_db_table: str, new_db_table: str) -> None:
        sf_managed_model = getattr(model._meta.auto_field, 'sf_managed_model', False)
        if sf_managed_model:
            self.check_permissions(model)
            if new_db_table != old_db_table:
                # TODO implement it by renameMetadata()
                raise NotImplementedError("df_table rename is not yet implemented")
            body = UPDATE_OBJECT_BODY.format(body=to_xml(self.make_model_metadata(model), indent=4))
            import pdb; pdb.set_trace()
            response_text = self.metadata_command(action='update', body=body)
            import pdb; pdb.set_trace()

    @wrap_debug
    def add_field(self, model: Type[Model], field: Field) -> None:
        sf_managed = getattr(field, 'sf_managed', False) or model._meta.db_table == 'django_migrations__c'
        if sf_managed:
            full_name = model._meta.db_table + '.' + field.column
            metadata = self.make_field_metadata(field)
            data = {'Metadata': metadata, 'FullName': full_name}

            log.debug("add_field %s %s", model, full_name)
            ret = self.request('POST', 'tooling/sobjects/CustomField', json=data)
            # if the error message is "SalesforceError: JSON_PARSER_ERROR ... at [line:1, column:39]
            # then the first invalid character is before the end of
            #     `json.dumps(data['Metadata'], separators=(',', ':'))[:column]`
            # maybe in the half of word
            assert ret.status_code == 201
            # ret.json() == {'id': '00NM0000002KYDHMA4', 'success': True, 'errors': [], 'warnings': [], 'infos': []}

            # FeldPermissions.objects.create(sobject_type='Donation__c', field='Donation__c.Amount__c',
            #                                permissions_edit=True, permissions_read=True, parent=ps)
            if not metadata.get('required'):
                field_permissions_data = {
                    'SobjectType': model._meta.db_table,
                    'Field': full_name,
                    'ParentId': self.permission_set_id,
                    'PermissionsEdit': True,
                    'PermissionsRead': True,
                }
                ret = self.request('POST', 'sobjects/FieldPermissions', json=field_permissions_data)
                assert ret.status_code == 201

    @wrap_debug
    @no_destructive_production
    def remove_field(self, model: Type[Model], field: Field) -> None:
        sf_managed_field = getattr(field, 'sf_managed', False)
        if sf_managed_field:
            full_name = model._meta.db_table + '.' + field.column
            log.debug("remove_field %s %s", model, full_name)
            self.delete_metadata('CustomField', full_name)

    @wrap_debug
    def alter_field(self, model: Type[Model], old_field: Field, new_field: Field, strict: bool = False
                    ) -> None:
        return self._alter_field(model, old_field, new_field, strict)

    def _alter_field(self, model: Type[Model], old_field: Field, new_field: Field, strict: bool = False
                     ) -> None:
        """This can rename a field or change the type or the parameters"""
        if new_field.column == 'Name':
            return self.alter_db_table(model, model._meta.db_table, model._meta.db_table)
        sf_managed_field = getattr(old_field, 'sf_managed', False) or getattr(new_field, 'sf_managed', False)
        if sf_managed_field:
            if model._meta.db_table.endswith('__c'):
                soql = "select RunningUserEntityAccessId from EntityDefinition where QualifiedApiName = %s limit 2"
                self.cur.execute(soql, [model._meta.db_table], tooling_api=True)
                rows = self.cur.fetchall()
                assert len(rows) == 1
                table_enum_or_id = rows[0][0].split('.')[0]
            else:
                table_enum_or_id = model._meta.db_table
            developer_name = self.developer_name(old_field.column)
            self.cur.execute("select Id from CustomField where TableEnumOrId = %s and DeveloperName = %s",
                             [table_enum_or_id, developer_name], tooling_api=True)
            field_id, = self.cur.fetchone()
            full_name = model._meta.db_table + '.' + new_field.column
            metadata = self.make_field_metadata(new_field)
            data = {'Metadata': metadata, 'FullName': full_name}
            log.debug("alter_field %s %s to %s", model, old_field, full_name)
            ret = self.request('PATCH', 'tooling/sobjects/CustomField/{}'.format(field_id), json=data)
            assert ret.status_code == 204

    def execute(self, sql: Union[Statement, str], params: Any = ()) -> None:
        assert isinstance(sql, str)
        raise NotSupportedError("Migration SchemaEditor: %r, %r" % (sql, params))

    # -- private methods

    @staticmethod
    def developer_name(api_name: str) -> str:
        return api_name.rsplit('__', 1)[0]

    @property
    def permission_set_id(self) -> str:
        if not self._permission_set_id:
            self.cur.execute("select Id from PermissionSet where Name = %s", ['Django_Salesforce'])
            rows = self.cur.fetchall()
            if rows:
                self._permission_set_id, = rows[0]
            else:
                raise OperationalError("Can not migrate because the Permission Set 'Django_Salesforce' doesn't exist")
        return self._permission_set_id

    @property
    def is_production(self):
        if self._is_production is None:
            self.cur.execute("select OrganizationType, IsSandbox from Organization")
            organization_type, is_sandbox = self.cur.fetchone()
            self._is_production = organization_type != 'Developer Edition' and not is_sandbox
        return self._is_production

    def get_object_permissions(self, db_table: str) -> Dict[str, bool]:
        cur = self.conn.cursor(dict)
        soql = ("SELECT Id, PermissionsCreate, PermissionsDelete, PermissionsRead, PermissionsEdit, "
                "       PermissionsViewAllRecords, PermissionsModifyAllRecords "
                "FROM ObjectPermissions WHERE ParentId = %s AND SobjectType = %s")
        cur.execute(soql, [self.permission_set_id, db_table])
        row = cur.fetchone()
        if row is None:
            row = {x[0]: False for x in cur.description if x[0] != 'Id'}
        return row

    def check_permissions(self, model: Type[Model]) -> None:
        no_check_permissions = self.connection.migrate_options.get('no_check_permissions')
        if not no_check_permissions:
            if not self.get_object_permissions(model._meta.db_table)['PermissionsModifyAllRecords']:
                raise IntegrityError("the model <model {}> is not enabled in Object Permisions "
                                     "to ModifyAll".format(model._meta.object_name))

    def metadata_command(self, action: str, body: str, is_async: bool = False) -> str:
        # TODO move to the driver
        data = METADATA_ENVELOPE.format(
            session_id=self.conn.sf_session.auth.get_auth()['access_token'],
            body=body,
        )
        self.cur.execute('select id from Organization')
        org_id, = self.cur.fetchone()
        url = '{instance_url}/services/Soap/m/{api_version}/{org_id}'.format(
            instance_url=self.conn.sf_auth.instance_url,
            api_version=self.conn.api_ver,
            org_id=org_id,
        )
        headers = {'SOAPAction': '""', 'Content-Type': 'text/xml; charset=utf-8'}
        # the header {'Expect': '100-continue'} is useful if sending much data and want
        # to check headers by the server before uploading the body
        ret = requests.request('POST', url, data=data.encode('utf-8'), headers=headers)
        async_progress = is_async and '<state>InProgress</state>' in ret.text
        if ret.status_code != 200 or 'success>true</success>' not in ret.text and not async_progress:
            # TODO parse xml for a better error message
            raise SalesforceError("Failed metadata {action}, code: {status_code}, response {text!r}".format(
                action=action, status_code=ret.status_code, text=ret.text
            ))
        return ret.text

    def make_field_metadata(self, field: Field) -> Dict[str, Any]:
        # TODO test all db_type with a default value and without
        db_type = field.db_type(self.connection)
        metadata = {
            'label': field.verbose_name,
            'type': db_type,
            'inlineHelpText': field.help_text,
            'required': not field.null,
            'unique': field.unique,  # type: ignore[attr-defined]
        }
        if isinstance(field.default, defaults.BaseDefault):
            # for backward compatibility of models
            if not isinstance(field.default, defaults.CallableDefault) and len(field.default.args) == 1:
                metadata['defaultValue'] = field.default.args[0]
        elif field.default is not None and field.default is not NOT_PROVIDED:
            metadata['defaultValue'] = field.default

        # by db_type
        if db_type == 'Checkbox':
            del metadata['required']
            assert 'defaultValue' in metadata
        elif db_type in ('Date', 'DateTime'):
            pass
        elif db_type == 'Number':
            metadata['precision'] = field.max_digits  # type: ignore[attr-defined]
            metadata['scale'] = field.decimal_places  # type: ignore[attr-defined]
        elif db_type in ('Text', 'Email', 'URL'):
            metadata['length'] = field.max_length
        elif db_type == 'Lookup':
            metadata.pop('defaultValue', None)  # TODO maybe write a warning if a defaultValue exists
            metadata['referenceTo'] = field.related_model._meta.db_table  # type: ignore[union-attr]
            metadata['relationshipName'] = field.remote_field.get_accessor_name()  # type: ignore[attr-defined]
            # metadata['relationshipLabel'] = metadata['relationshipName']  # not important
            metadata['deleteConstraint'] = (
                'Restrict' if field.remote_field.on_delete is PROTECT  # type: ignore[attr-defined]
                else 'SetNull')
        elif db_type == 'Picklist':
            # deactivated Picklist values are not visible by a normal metadata query
            # we don't need to work with them
            metadata['valueSet'] = {
                'restricted': False,
                'valueSetDefinition': {
                    'sorted': False,
                    'value': [
                        {
                            'fullName': ch_name,
                            'label': ch_label,
                            'default': ch_name == field.default,
                        }
                        for ch_name, ch_label in field.choices
                    ],
                }
            }
        else:
            raise NotImplementedError
        return metadata

    def make_model_metadata(self, model: Type[Model]) -> Dict[str, Any]:
        for field in model._meta.fields:
            if field.column == 'Name':
                name_field = field
                break
        else:
            name_field = None
        name_writable = getattr(name_field, 'sf_read_only', 3) == 0
        name_label = getattr(name_field, 'name', 'Name')
        name_metadata = {
            'label': name_label,
            'type': 'Text' if name_writable else 'AutoNumber',
        }
        if not name_writable:
            name_metadata['displayFormat'] = self.DISPLAY_FORMAT
        metadata = {
            'fullName': model._meta.db_table,
            'label': model._meta.verbose_name,
            'pluralLabel': str(model._meta.verbose_name_plural),
            'deploymentStatus': 'Deployed',
            'sharingModel': 'ReadWrite',
            'nameField': name_metadata,
        }
        return metadata

    def delete_metadata(self, metadata_type: str, full_name: str) -> None:
        # can be modified to a list of custom fields field names
        # If we want purgeOnDelete read this:
        # https://salesforce.stackexchange.com/questions/68798/using-metadata-api-to-deploy-destructive-changes-to-delete-custom-fields
        # https://salesforce.stackexchange.com/questions/69926/deleting-custom-object-via-destructivechanges-xml-and-metadata-api-deploy
        body = DELETE_METADATA_BODY.format(metadata_type=metadata_type, custom_object_name=full_name)
        self.metadata_command(action='delete', body=body)

    def wait_for_entity(self, db_table: str, deploy_result_id: str) -> str:
        t0 = time.time()
        dt = 0.05
        # wait for table creation
        cur2 = self.conn.cursor(dict)
        while True:
            if time.time() - t0 > 30:
                raise TimeoutError()
            time.sleep(dt)
            dt *= 1.2
            soql = ("select DeveloperName, Label, QualifiedApiName, DeploymentStatus, RunningUserEntityAccessId "
                    "from EntityDefinition where QualifiedApiName = %s limit 2")
            cur2.execute(soql, [db_table], tooling_api=True)
            rows = cur2.fetchall()
            if rows:
                assert len(rows) == 1
                entity_id = rows[0]['RunningUserEntityAccessId'].split('.')[0]
                wait_elapsed = round(time.time() - t0, 3)
                log.debug('create_model %s; time:%f, pk:%s, rows:%s', db_table, wait_elapsed, deploy_result_id, rows)
                break
        return entity_id
