"""
Tests that do not need to connect servers
"""
# pylint:disable=deprecated-method,too-many-ancestors,unused-variable

from django.apps.registry import Apps
from django.test import TestCase
from django.db.models import DO_NOTHING
from salesforce import fields, models
from salesforce.testrunner.example.models import (
        Contact, Opportunity, OpportunityContactRole, ChargentOrder)
from salesforce.backend.test_helpers import LazyTestMixin


class EasyCharField(models.CharField):
    def __init__(self, max_length=255, null=True, default='', **kwargs):
        super(EasyCharField, self).__init__(max_length=max_length, null=null, default=default, **kwargs)


class EasyForeignKey(models.ForeignKey):
    def __init__(self, othermodel, on_delete=DO_NOTHING, **kwargs):
        super(EasyForeignKey, self).__init__(othermodel, on_delete=on_delete, **kwargs)


class TestField(TestCase):
    """
    Unit tests for salesforce.fields that don't need to connect Salesforce.
    """
    def test_primary_key(self):
        """
        Verify the expected attributes of primary key
        """
        test_apps = Apps(['salesforce.testrunner.example'])

        class Ab(models.SalesforceModel):
            class Meta:
                app_label = 'example'
                apps = test_apps
        self.assertTrue(isinstance(fields.SF_PK, str))
        self.assertTrue(hasattr(Ab(), 'pk'))
        self.assertTrue(hasattr(Ab(), fields.SF_PK))

    def test_auto_db_column(self):
        """
        Verify that db_column is not important in most cases, but it has
        precedence if it is specified.
        Verify it for lower_case and CamelCase conventions, for standard fields
        and for custom fields, for normal fields and for foreign keys.
        """
        test_apps = Apps(['salesforce.testrunner.example'])

        class Aa(models.SalesforceModel):
            class Meta:
                app_label = 'example'
                apps = test_apps

        class Dest(models.SalesforceModel):
            class Meta:
                app_label = 'example'
                apps = test_apps

        def test(field, expect_attname, expect_column):
            "Compare field attributes with expected `attname` and `column`."
            field.contribute_to_class(Dest, field.name)
            self.assertEqual(field.get_attname_column(), (expect_attname, expect_column))
        # Normal fields
        test(EasyCharField(name='LastName'), 'LastName', 'LastName')
        test(EasyCharField(name='last_name'), 'last_name', 'LastName')
        test(EasyCharField(name='MyCustomField', custom=True), 'MyCustomField', 'MyCustomField__c')
        test(EasyCharField(name='MyCustomField', custom=True, db_column='UglyName__c'), 'MyCustomField', 'UglyName__c')
        test(EasyCharField(name='my_custom_field', custom=True), 'my_custom_field', 'MyCustomField__c')
        test(EasyCharField(name='Payment_Method', custom=True), 'Payment_Method', 'Payment_Method__c')
        # Foreign keys to a class Aa
        test(EasyForeignKey(Aa, name='Account'), 'AccountId', 'AccountId')
        test(EasyForeignKey(Aa, name='account'), 'account_id', 'AccountId')
        test(EasyForeignKey(Aa, name='account', db_column='AccountId'), 'account_id', 'AccountId')
        test(EasyForeignKey(Aa, name='account', db_column='UglyNameId'), 'account_id', 'UglyNameId')
        test(EasyForeignKey(Aa, name='CampaignMember'), 'CampaignMemberId', 'CampaignMemberId')
        test(EasyForeignKey(Aa, name='campaign_member'), 'campaign_member_id', 'CampaignMemberId')
        test(EasyForeignKey(Aa, name='MyCustomForeignField', custom=True),
             'MyCustomForeignFieldId',
             'MyCustomForeignField__c')
        test(EasyForeignKey(Aa, name='my_custom_foreign_field', custom=True),
             'my_custom_foreign_field_id',
             'MyCustomForeignField__c')


class TestQueryCompiler(TestCase, LazyTestMixin):
    def test_namespaces_auto(self):
        """Verify that the database column name can be correctly autodetected

        from model Meta for managed packages with a namespace prefix.
        (The package need not be installed for this unit test.)
        """
        tested_field = ChargentOrder._meta.get_field('Balance_Due')
        self.assertEqual(tested_field.sf_custom, True)
        self.assertEqual(tested_field.column, 'ChargentOrders__Balance_Due__c')

    def test_subquery_condition(self):
        """Regression test with a filter based on subquery.

        This test is very similar to the required example in PR #103.
        """
        qs = OpportunityContactRole.objects.filter(
            role='abc',
            opportunity__in=Opportunity.objects.filter(stage='Prospecting')
        )
        sql, params = qs.query.get_compiler('salesforce').as_sql()
        self.assertRegexpMatches(sql,
                                 "WHERE Opportunity.StageName =",
                                 "Probably because aliases are invalid for SFDC, e.g. 'U0.StageName'")
        self.assertRegexpMatches(sql,
                                 r'SELECT .*OpportunityContactRole\.Role.* '
                                 r'FROM OpportunityContactRole WHERE \(.* AND .*\)')
        self.assertRegexpMatches(sql,
                                 r'OpportunityContactRole.OpportunityId IN '
                                 r'\(SELECT Opportunity\.Id FROM Opportunity WHERE Opportunity\.StageName = %s ?\)')
        self.assertRegexpMatches(sql, 'OpportunityContactRole.Role = %s')

    def test_none_method_queryset(self):
        """Test that none() method in the queryset returns [], not error"""
        with self.lazy_assert_n_requests(0, "No database requests should be run for .none() method"):
            self.assertEqual(tuple(Contact.objects.none()), ())
            self.assertEqual(tuple(Contact.objects.all().none().all()), ())
            self.assertTrue('[]' in repr(Contact.objects.none()))
        self.lazy_check()


class TestTopologyCompiler(TestCase):
    def assertTopo(self, alias_map_items, expected):
        compiler = Contact.objects.none().query.get_compiler('salesforce')
        ret = compiler.query_topology(alias_map_items)
        self.assertEqual(ret, expected)

    def test_topology_compiler(self):
        # Contact.objects.all()
        # SELECT Contact.Id FROM Contact
        self.assertTopo([(None, 'Contact', None, 'Contact')], {'Contact': 'Contact'})
        # Custom.objects.all()
        # SELECT Custom__c.Id FROM Custom__c
        self.assertTopo([(None, 'Custom__c', None, 'Custom__c')], {'Custom__c': 'Custom__c'})
        # C (Id, PId) - child, P (Id) - parent
        # C.objects.filter(p__namen='xy')
        # SELECT C.Id, C.PId FROM C WHERE C.P.Name='abc'
        self.assertTopo([(None, 'C', None, 'C'), ('C', 'P', (('PId', 'Id'),), 'P')], {'C': 'C', 'P': 'C.P'})

    def test_normal2custom(self):
        # qs = Attachment.objects.filter(parent__name='abc')
        # self.assertTopo()
        # "SELECT Attachment.Id FROM Attachment WHERE Attachment.Parent.Name = 'abc'"
        self.assertTopo([('C', 'P__c', (('PId', 'Id'),), 'P__c'), (None, 'C', ((None, None),), 'C')],
                        {'P__c': 'C.P', 'C': 'C'})

    def test_custom2normal(self):
        # qs = Test.objects.filter(contact__last_name='Johnson')
        # ret = qs.query.get_compiler('salesforce').query_topology()
        # "SELECT ... FROM django_Test__c WHERE django_Test__c.Contact__r.LastName = 'Johnson'")
        self.assertTopo([(None, 'C__c', None, 'C__c'), ('C__c', 'P', (('P__c', 'Id'),), 'P')],
                        {'C__c': 'C__c', 'P': 'C__c.P__r'})

    def test_many2many(self):
        # C (Id, AId, BId) - child,  A (Id) - first parent, B (Id) - second parent
        alias_map_items = [
            (None, 'A', None, 'A'),
            ('A', 'C', (('Id', 'AId'),), 'C'),
            ('C', 'B', (('BId', 'Id'),), 'B')]
        self.assertTopo(alias_map_items, {'C': 'C', 'A': 'C.A', 'B': 'C.B'})
