"""
Minimal code to support ignored makemigrations  (like django.db.backends.*.schema)

without interaction to SF (without migrate)
"""
from typing import Any, Dict, Type, Union
import logging
import re
import time

import requests
from django.db import NotSupportedError
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.backends.ddl_references import Statement
from django.db.models import Field, Model, PROTECT
from salesforce.dbapi.exceptions import SalesforceError

log = logging.getLogger(__name__)

# souce: https://gist.github.com/wadewegner/9139536
METADATA_ENVELOPE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:apex="http://soap.sforce.com/2006/08/apex"
                  xmlns:cmd="http://soap.sforce.com/2006/04/metadata"
                  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Header>
    <cmd:SessionHeader>
      <cmd:sessionId>{session_id}</cmd:sessionId>
    </cmd:SessionHeader>
  </soapenv:Header>
  <soapenv:Body>
{body}
  </soapenv:Body>
</soapenv:Envelope>
"""

CREATE_OBJECT_BODY = """
    <create xmlns="http://soap.sforce.com/2006/04/metadata">
      <metadata xsi:type="CustomObject">
        <fullName>{full_name}</fullName>
        <label>{label}</label>
        <pluralLabel>{plural_label}</pluralLabel>
        <deploymentStatus>Deployed</deploymentStatus>
        <sharingModel>ReadWrite</sharingModel>
        <nameField>
           <label>ID</label>
           <type>AutoNumber</type>
        </nameField>
      </metadata>
    </create>
"""

DELETE_METADATA_BODY = """
    <cmd:deleteMetadata>
      <cmd:type>{metadata_type}</cmd:type>
      <cmd:fullNames>{custom_object_name}</cmd:fullNames>
    </cmd:deleteMetadata>
"""


class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):
    # pylint:disable=abstract-method  # undefined: prepare_default, quote_value

    def __init__(self, connection, collect_sql=False, atomic=True):
        self.conn = connection.connection
        self.connection = connection.connection
        self.collect_sql = collect_sql
        # if self.collect_sql:
        #    self.collected_sql = []
        log.debug('DatabaseSchemaEditor __init__')
        self.cur = self.conn.cursor()
        self.request = self.conn.handle_api_exceptions
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

    def create_model(self, model: Type[Model]) -> None:
        if model._meta.db_table == 'django_migrations':
            model._meta.db_table += '__c'
        db_table = model._meta.db_table
        sf_managed = getattr(model._meta, 'sf_managed', False) or model._meta.db_table == 'django_migrations__c'
        if sf_managed:
            body = CREATE_OBJECT_BODY.format(
                full_name=db_table,
                label=model._meta.verbose_name,
                plural_label=model._meta.verbose_name_plural,
            )
            text = self.metadata_command(action='create', body=body)
            cur = self.cur
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
            match = re.match(r'.*<id>([0-9A-Za-z]{18})</id>', text)
            assert match
            # how to use the Id?
            pk = match.group(1)
            t0 = time.time()
            dt = 0.05
            # wait for table creation
            while True:
                if time.time() - t0 > 30:
                    raise TimeoutError()
                time.sleep(dt)
                dt *= 1.2
                soql = "select DeveloperName from CustomObject where DeveloperName = %s limit 2"
                soql = ("select DeveloperName, Label, QualifiedApiName, DeploymentStatus, RunningUserEntityAccessId "
                        "from EntityDefinition where QualifiedApiName = %s limit 2")
                cur.execute(soql, [model._meta.db_table], tooling_api=True)
                rows = cur.fetchall()
                if rows:
                    assert len(rows) == 1
                    entity_id = rows[0]['RunningUserEntityAccessId'].split('.')[0]
                    log.debug('create_model %s; time:%f, pk:%s, rows:%s', db_table, round(time.time() - t0, 3), pk, rows)
                    break

            cur.execute("select Id from PermissionSet where Label = %s", ['Django Salesforce'])
            ps_id = cur.fetchone()['Id']
            object_permissions_data = dict(
                # selection by `db_table` was be not reliable if the same object is in the trash
                SobjectType=entity_id,
                ParentId=ps_id,
                # PermissionsViewAllRecords=True,
                # PermissionsModifyAllRecords=True,
                PermissionsRead=True,
                PermissionsEdit=True,
                # PermissionsCreate=True,
                # PermissionsDelete=True
            )
            ret = self.request('POST', 'sobjects/ObjectPermissions', json=object_permissions_data)
            assert ret.status_code == 201

        for field in model._meta.fields:
            sf_managed_field = (getattr(field, 'sf_managed', False) or db_table == 'django_migrations__c'
                                and field.column.lower() != 'id')
            if sf_managed_field:
                import pdb; pdb.set_trace()
                if db_table == 'django_migrations__c':
                    field.column += '__c'
                self.add_field(model, field)

    def delete_model(self, model: Type[Model]) -> None:
        if model._meta.db_table == 'django_migrations':
            model._meta.db_table += '__c'
        sf_managed = getattr(model._meta, 'sf_managed', False) or model._meta.db_table == 'django_migrations__c'
        if sf_managed:
            import pdb; pdb.set_trace()
            self.delete_metadata('CustomObject', model._meta.db_table)
        else:
            for field in model._meta.fields:
                sf_managed_field = getattr(field, 'sf_managed', False)
                if sf_managed_field:
                    import pdb; pdb.set_trace()
                    self.remove_field(model, field)

    def add_field(self, model: Type[Model], field: Field) -> None:
        sf_managed = getattr(field, 'sf_managed', False) or model._meta.db_table == 'django_migrations__c'
        if sf_managed:
            full_name = model._meta.db_table + '.' + field.column
            metadata = self.make_field_metadata(field)
            data = {'Metadata': metadata, 'FullName': full_name}

            log.debug("add field %s %s", model, field)
            ret = self.request('POST', 'tooling/sobjects/CustomField', json=data)
            assert ret.status_code == 201
            # ret.json() == {'id': '00NM0000002KYDHMA4', 'success': True, 'errors': [], 'warnings': [], 'infos': []}

            self.cur.execute("select Id from PermissionSet where Label = %s", ['Django Salesforce'])
            ps_id, = self.cur.fetchone()

            # FeldPermissions.objects.create(sobject_type='Donation__c', field='Donation__c.Amount__c',
            #                                permissions_edit=True, permissions_read=True, parent=ps)
            if not metadata['required']:
                field_permissions_data = {
                    'SobjectType': model._meta.db_table,
                    'Field': full_name,
                    'ParentId': ps_id,
                    'PermissionsEdit': True,
                    'PermissionsRead': True,
                }
                ret = self.request('POST', 'sobjects/FieldPermissions', json=field_permissions_data)
                assert ret.status_code == 201

    def remove_field(self, model: Type[Model], field: Field) -> None:
        sf_managed = getattr(field, 'sf_managed', False)
        if sf_managed:
            full_name = model._meta.db_table + '.' + field.column
            self.delete_metadata('CustomField', full_name)
            # developer_name = field.column.rsplit('__', 1)[0]
            # self.cur.execute("select Id from CustomField where TableEnumOrId = %s and DeveloperName = %s",
            #                  [model._meta.db_table, developer_name],
            #                   tooling_api=True)
            # pk, = self.cur.fetchone()
            # # SalesforceError: INSUFFICIENT_ACCESS_ON_CROSS_REFERENCE_ENTITY
            # ret = self.request('DELETE', 'tooling/sobjects/CustomField/{}'.format(pk))
            # assert ret and ret.status_code == 204

    def alter_field(self, model: Type[Model], old_field: Field, new_field: Field, strict: bool = False
                    ) -> None:
        """This can rename a field or change the type or the parameters"""
        sf_managed = getattr(old_field, 'sf_managed', False) or getattr(new_field, 'sf_managed', False)
        if sf_managed:
            developer_name = old_field.column.rsplit('__', 1)[0]
            self.cur.execute("select Id from CustomField where TableEnumOrId = %s and DeveloperName = %s",
                             [model._meta.db_table, developer_name],
                             tooling_api=True)
            field_id, = self.cur.fetchone()
            full_name = model._meta.db_table + '.' + new_field.column
            metadata = self.make_field_metadata(new_field)
            data = {'Metadata': metadata, 'FullName': full_name}
            ret = self.request('PATCH', 'tooling/sobjects/CustomField/{}'.format(field_id), json=data)
            assert ret.status_code == 204

    def execute(self, sql: Union[Statement, str], params: Any = ()) -> None:
        assert isinstance(sql, str)
        import pdb; pdb.set_trace()
        if (sql == 'CREATE TABLE django_migrations ()'
                or sql.startswith('DROP TABLE ')) and not params:
            return
        raise NotSupportedError("Migration SchemaEditor: %r, %r" % (sql, params))

    # -- private methods

    def metadata_command(self, action: str, body: str) -> str:
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
        headers = {'SOAPAction': action, 'Content-Type': 'text/xml; charset=utf-8'}
        # the header {'Expect': '100-continue'} is useful if sending much data and want
        # to check headers by the server before uploading the body
        ret = requests.request('POST', url, data=data, headers=headers)
        if ret.status_code != 200 or 'success>true</success>' not in ret.text:
            raise SalesforceError("Failed metadata {action}, code: {status_code}, response {text!r}".format(
                action=action, status_code=ret.status_code, text=ret.text
            ))
        return ret.text

    def make_field_metadata(self, field: Field) -> Dict[str, Any]:
        db_type = field.db_type(self.connection)
        metadata = {
            'label': field.verbose_name,
            'type': db_type,
            'inlineHelpText': field.help_text,
            'required': not field.null,
            'unique': field.unique,  # type: ignore[attr-defined]
        }
        # if
        #    metadata['defaultValue'] =

        # by db_type
        if db_type == 'CheckBox':
            del metadata['required']
        elif db_type in ('Date', 'DateTime'):
            pass
        elif db_type == 'Number':
            metadata['precision'] = field.decimal_places  # type: ignore[attr-defined]
            metadata['length'] = field.scale  # type: ignore[attr-defined] # TODO
        elif db_type in ('Text', 'Email', 'URL'):
            metadata['length'] = field.max_length
        elif db_type == 'Lookup':
            del metadata['defaultValue']
            # TODO "Related List Label" "Child Relationship Name"
            metadata['relatedTo'] = field.related_model._meta.db_table  # type: ignore[union-attr]
            metadata['relationshipLabel'] = field.remote_field.get_accessor_name()  # type: ignore[attr-defined]
            metadata['deleteConstraint'] = (
                'Restrict' if field.remote_field.on_delete is PROTECT  # type: ignore[attr-defined]
                else 'SetNull')
        elif db_type == 'PickList':
            pass  # TODO copy from sf_syncdb
        else:
            raise NotImplementedError
        return metadata

    def delete_metadata(self, metadata_type: str, full_name: str) -> None:
        # can be modified to a list of custom fields field names
        body = DELETE_METADATA_BODY.format(metadata_type=metadata_type, custom_object_name=full_name)
        self.metadata_command(action='delete', body=body)
