"""
Minimal code to support ignored makemigrations  (like django.db.backends.*.schema)

without interaction to SF (without migrate)
"""
import re
import requests
import time
from django.db import NotSupportedError
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

from salesforce.backend import log

CREATE_OBJECT = """<?xml version="1.0" encoding="UTF-8"?>
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
   </soapenv:Body>
</soapenv:Envelope>
"""


class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):
    # pylint:disable=abstract-method  # undefined: prepare_default, quote_value

    def __init__(self, connection, collect_sql=False, atomic=True):
        self.conn = connection.connection
        self.connection = connection.connection
        self.collect_sql = collect_sql
        # if self.collect_sql:
        #    self.collected_sql = []
        # print('** DatabaseSchemaEditor __init__')
        self.cur = self.conn.cursor()
        self.request = self.conn.handle_api_exceptions
        super().__init__(connection, collect_sql=collect_sql, atomic=atomic)

    # State-managing methods

    def __enter__(self):
        # print('** DatabaseSchemaEditor __enter__')
        self.deferred_sql = []  # pylint:disable=attribute-defined-outside-init
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # print('** DatabaseSchemaEditor __exit__')
        if exc_type is None:
            for sql in self.deferred_sql:
                self.execute(sql)

    def create_model(self, model):
        if model._meta.db_table == 'django_migrations':
            model._meta.db_table += '__c'
        db_table = model._meta.db_table
        data = CREATE_OBJECT.format(
            session_id=self.conn.sf_session.auth.get_auth()['access_token'],
            full_name=db_table,
            label=model._meta.verbose_name,
            plural_label=model._meta.verbose_name_plural,
        )
        self.cur.execute('select id from Organization')
        org_id, = self.cur.fetchone()
        url = '{instance_url}/services/Soap/m/{api_version}/{org_id}'.format(
            instance_url=self.conn.sf_auth.instance_url,
            api_version=self.conn.api_ver,
            org_id=org_id,
        )
        headers = {'SOAPAction': 'create', 'Content-Type': 'text/xml; charset=utf-8', 'Expect': '100-continue'}
        cur = self.conn.cursor(dict)
        ret = requests.request('POST', url, data=data, headers=headers)
        assert ret.status_code == 200
        print(ret.text)
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
        match = re.match(r'.*<id>([0-9A-Za-z]{18})</id>', ret.text)
        # how to use the Id?
        pk = match.group(1)
        t0 = time.time()
        dt = 0.05
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
                print('OK time{}, pk:{}, rows:{}'.format(round(time.time() - t0, 3), pk, rows))
                break

        cur.execute("select Id from PermissionSet where Label = %s", ['Django Salesforce'])
        ps_id = cur.fetchone()['Id']
        object_permissions_data = dict(
            SobjectType=entity_id,  # `db_table` would be not reliable if the same object is in the trash
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
            if field.column.lower() == 'id':
                continue
            if db_table == 'django_migrations__c':
                field.column += '__c'
                # field.db_column += '__c'
            self.add_field(model, field)

    def add_field(self, model, field):
        sf_managed = getattr(field, 'sf_managed', False) or model._meta.db_table == 'django_migrations__c'
        db_type = field.db_type(self.connection)
        if sf_managed:
            full_name = model._meta.db_table + '.' + field.column
            metadata = {
                'label': field.verbose_name,
                'type': db_type,
                'inlineHelpText': field.help_text,
                'required': not field.null,
                'unique': field.unique,
            }
            if db_type == 'Text':
                metadata['length'] = field.max_length
            elif db_type == 'DateTime':
                pass
            else:
                import pdb; pdb.set_trace()
                raise NotImplementedError

            data = {
                'Metadata': metadata,
                'FullName': full_name,
            }
            print(f"** add field {model} {field}")
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

    def remove_field(self, model, field):
        sf_managed = getattr(field, 'sf_managed', False)
        if sf_managed:
            full_name = model._meta.db_table + '.' + field.column
            self.cur.execute("select Id from CustomField where FullName = %s", full_name)
            pk, = self.cur.fetchone()
            ret = self.request('DELETE', 'tooling/sobjects/CustomField', pk)
            assert ret and ret.status_code == 204

    def alter_field(self, model, old_field, new_field, strict=False):
        import pdb; pdb.set_trace()
        sf_managed = getattr(old_field, 'sf_managed', False) or getattr(new_field, 'sf_managed', False)
        if sf_managed:
            print(f"\n** alter field {model} {old_field} {new_field}")

    def execute(self, sql, params=()):
        if (sql == 'CREATE TABLE django_migrations ()'
                or sql.startswith('DROP TABLE ')) and not params:
            return
        raise NotSupportedError("Migration SchemaEditor: %r, %r" % (sql, params))
