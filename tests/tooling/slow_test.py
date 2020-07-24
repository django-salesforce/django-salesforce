"""Test the completness ad validity of tooling inspectdb by read and write all tables.

It tries to find model and read one record from all retrieveable tables, except
objects with extraordinal filter conditions. Then it tries to write this
record back if the table is updateable, except some tables. This can fail
on permissions.

Usage:
$ python manage.py inspectdb --database=salesforce --tooling-api --settings=tests.tooling.settings \
        >tests/tooling/models.py
$ python manage.py check --settings=tests.tooling.settings
$ python tests/tooling/slow_test.py
"""

from inspect import isclass
from sys import stdout, stderr
import os
import sys

import django
sys.path.insert(0, '.')
os.environ['DJANGO_SETTINGS_MODULE'] = 'tests.tooling.settings'

django.setup()

# these 3 lines must be imported after: path, environ, django.setup()
from django.db import connections  # NOQA
from tests.tooling import models as mdl  # NOQA
from salesforce.backend.base import SalesforceError  # NOQA


# see https://developer.salesforce.com/docs/atlas.en-us.api_tooling.meta/api_tooling/reference_objects_soql_limits.htm
# "The following objects in Tooling API don’t support SOQL operations
#  COUNT(), GROUP BY, LIMIT, LIMIT OFFSET, OR, NOT, and INCLUDES."
soql_operation_limitation = [
    'CompactLayoutInfo', 'CompactLayoutItemInfo', 'DataType', 'EntityDefinition',
    'EntityLimit', 'EntityParticle', 'FieldDefinition', 'Publisher', 'RelationshipDomain',
    'RelationshipInfo', 'SearchLayout', 'ServiceFieldDataType', 'StandardAction',
    'TimeSheetTemplate', 'UserEntityAccess', 'UserFieldAccess',
]

sf = connections['salesforce']


def run():
    start_name = sys.argv[1] if sys.argv[1:] else ''
    sf.introspection.is_tooling_api = True
    n_tables = n_read = n_no_data = n_read_errors = n_write = n_write_errors = 0
    model_map = {cls._meta.db_table: cls
                 for cls in mdl.__dict__.values()
                 if isclass(cls) and issubclass(cls, django.db.models.Model)
                 }
    problematic_read = {
        # document in a private folder
        'EmailTemplate',
        # only queries of the form Id='<some_value>'
        'SubscriberPackage', 'SubscriberPackageVersion',

        # "When retrieving results with Metadata or FullName fields, the query
        #  qualifications must specify no more than one row for retrieval."
        'EntityDefinition',
        # invalid Metadata JSON
        'OpportunitySettings',
        # any reason
        'AIReplyRecommendationsSettings', 'AccountInsightsSettings', 'ActivitiesSettings',
        'ApexExecutionOverlayResult', 'AutomatedContactsSettings', 'BusinessHoursEntry',
        'CaseClassificationSettings', 'CompactLayoutInfo', 'CompactLayoutItemInfo',
        'DataDotComSettings', 'EinsteinAssistantSettings', 'EmailToCaseRoutingAddress',
        'EntityLimit', 'FieldServiceSettings', 'ForecastingObjectListSelectedSettings',
        'ForecastingObjectListSettings', 'FormulaVariable', 'HighVelocitySalesSettings',
        'IndustriesManufacturingSettings', 'KnowledgeAnswerSettings', 'KnowledgeCaseField',
        'KnowledgeCaseSettings', 'KnowledgeLanguageSettings', 'KnowledgeSettings',
        'KnowledgeSuggestedArticlesSettings', 'KnowledgeWorkOrderField',
        'KnowledgeWorkOrderLineItemField', 'LiveAgentSettings', 'MenuItem',
        'ObjectSearchSetting', 'OpportunityInsightsSettings',
        'OpportunityListFieldsLabelMapping', 'OpportunityScoreSettings',
        'OrderManagementSettings', 'StandardAction', 'StandardValueSet',
    }
    problematic_write = {
        # any SalesforceError
        'AccountIntelligenceSettings', 'AccountSettings', 'ActionsSettings',
        'AnalyticsSettings', 'ApexClass', 'ApexPage', 'ApexSettings', 'ApexTrigger',
        'AppExperienceSettings', 'BlockchainSettings', 'BusinessHoursSettings',
        'BusinessProcess', 'CampaignSettings', 'CaseSettings', 'ChatterEmailsMDSettings',
        'ChatterSettings', 'CommunitiesSettings', 'ConnectedAppSettings', 'ContentSettings',
        'CurrencySettings', 'DashboardMobileSettings', 'DeploymentSettings', 'EACSettings',
        'EmailAdministrationSettings', 'EmailIntegrationSettings', 'EmailTemplateSettings',
        'EnhancedNotesSettings', 'EventSettings', 'FilesConnectSettings', 'FlowSettings',
        'ForecastingSettings', 'ForecastingTypeSettings', 'FormulaSettings',
        'GoogleAppsSettings', 'IndustriesSettings', 'InvocableActionSettings',
        'IsvHammerSettings', 'LanguageSettings', 'LeadConfigSettings', 'LeadConvertSettings',
        'LightningExperienceSettings', 'MacroSettings', 'ManagedContentType',
        'MobileSettings', 'MyDomainSettings', 'NotificationsSettings', 'PardotSettings',
        'PartyDataModelSettings', 'PathAssistantSettings', 'PicklistSettings',
        'PlatformEncryptionSettings', 'PortalsSettings', 'PrivacySettings', 'ProductSettings',
        'QuickTextSettings', 'RecentlyViewed', 'RecordPageSettings', 'SchemaSettings',
        'SearchSettings', 'SecuritySettings', 'SharingSettings', 'SocialProfileSettings',
        'SurveySettings', 'SystemNotificationSettings', 'Territory2Settings',
        'TrialOrgSettings', 'User', 'UserEngagementSettings', 'UserInterfaceSettings',
        'UserManagementSettings', 'WebToXSettings', 'WorkDotComSettings',
        # ExpirationDate must be in the future.
        'TraceFlag',
        # silently not updated
        'CustomApplication', 'CustomField', 'CustomTab', 'FlexiPage', 'GlobalValueSet',
        'Layout', 'QuickActionDefinition', 'RemoteProxy', 'ValidationRule',
        'WorkflowFieldUpdate', 'WorkflowRule',
        'QuickActionListItem',
    }

    #  FIELD_INTEGRITY_EXCEPTION
    # Only the Metadata and FullName fields may be specified on AddressSettings, or else Metadata must be excluded.

    requires_filter = [
        # some of them are important, but can not be tested automatically here
        'ColorDefinition', 'EntityParticle', 'FieldDefinition', 'IconDefinition',
        'OwnerChangeOptionInfo', 'RelationshipDomain', 'RelationshipInfo', 'SearchLayout',
        'SiteDetail', 'UserEntityAccess', 'UserFieldAccess',
    ]
    new_problematic = []
    sf.connect()
    # cur = sf.connection.cursor()
    for tab in sf.introspection.table_list_cache['sobjects']:
        db_table = tab['name']
        if tab['queryable'] and (db_table in model_map and db_table not in requires_filter and
                                 db_table not in problematic_read):
            if db_table < start_name:
                continue
            test_class = model_map[db_table]
            stdout.write('%s' % db_table)
            obj = None
            try:
                n_read += 1
                # cur.execute("SELECT Id FROM {} LIMIT 1".format(db_table), tooling_api=True)
                obj = test_class.objects.all()[0]
            except SalesforceError as exc:
                new_problematic.append(db_table)
                stderr.write("\n************** %s %s\n" % (db_table, exc))
                n_read_errors += 1
            except IndexError:
                n_no_data += 1
            if obj:
                stdout.write("* ")
            if obj and tab['updateable'] and db_table not in problematic_write:
                stdout.write('(write) ')
                try:
                    n_write += 1
                    obj.save(force_update=True)
                except SalesforceError as exc:
                    new_problematic.append(db_table)
                    stderr.write("\n************** SalesforceError %s %s\n" % (db_table, exc))
                    n_write_errors += 1
                except (TypeError, NotImplementedError) as exc:
                    new_problematic.append(db_table)
                    stderr.write("\n************** %s %s %s\n" % (exc.__class__.__name__, db_table, exc))
                    n_write_errors += 1
                else:
                    # object 'Topic' doesn't have the attribute 'last_modified_date'
                    # in recently created SFDC databases (proably version 34.0+)
                    if hasattr(obj, 'last_modified_date'):
                        if not (test_class.objects.get(pk=obj.pk).last_modified_date > obj.last_modified_date):
                            new_problematic.append(db_table)
                            print("not updated - -")
                            n_write_errors += 1
            stdout.write('\n')
    if new_problematic:
        print("\nnew_problematic:\n%r\n" % new_problematic)
    n_tables = len(sf.introspection.table_list_cache['sobjects'])
    print('Result: {n_tables} tables, {n_read} reads tried, {n_no_data} no data, '
          '{n_read_errors} read errors, {n_write} writes tried, {n_write_errors} write errors'
          .format(n_tables=n_tables, n_read=n_read, n_no_data=n_no_data,
                  n_read_errors=n_read_errors, n_write=n_write, n_write_errors=n_write_errors))
    print('********* ERRORs found' if n_read_errors + n_write_errors else 'OK')
    return n_read_errors + n_write_errors == 0


if __name__ == '__main__':
    ok = run()
    sys.exit(0 if ok else 1)
