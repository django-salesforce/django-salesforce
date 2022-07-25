"""
Tests that do not need to connect servers
"""
# pylint:disable=unused-variable

from typing import Type
from django.apps.registry import Apps
from django.test import TestCase
from django.db.models import DO_NOTHING, Subquery
from salesforce import fields, models
from salesforce.dbapi import driver
from salesforce.testrunner.example.models import (
        Contact, Opportunity, OpportunityContactRole, ChargentOrder)
from salesforce.backend.test_helpers import default_is_sf, LazyTestMixin, skipUnless
from salesforce.backend.utils import sobj_id


class EasyCharField(models.CharField):
    def __init__(self, max_length=255, null=True, default='', **kwargs):
        super().__init__(max_length=max_length, null=null, default=default, **kwargs)


class EasyForeignKey(models.ForeignKey):
    def __init__(self, othermodel, on_delete=DO_NOTHING, **kwargs):
        super().__init__(othermodel, on_delete=on_delete, **kwargs)


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

    def test_subquery_filter_on_parent(self):
        """Regression test with a filter based on subquery.

        This test is very similar to the required example in PR #103.
        """
        qs = OpportunityContactRole.objects.filter(
            role='abc',
            opportunity__in=Opportunity.objects.filter(stage='Prospecting')
        )
        sql, params = qs.query.get_compiler('salesforce').as_sql()
        self.assertRegex(sql,
                         "WHERE Opportunity.StageName =",
                         "Probably because aliases are invalid for SFDC, e.g. 'U0.StageName'")
        self.assertRegex(sql,
                         r'SELECT .*OpportunityContactRole\.Role.* '
                         r'FROM OpportunityContactRole WHERE \(.* AND .*\)')
        self.assertRegex(sql,
                         r'OpportunityContactRole.OpportunityId IN '
                         r'\(SELECT Opportunity\.Id FROM Opportunity WHERE Opportunity\.StageName = %s ?\)')
        self.assertRegex(sql, 'OpportunityContactRole.Role = %s')

    @skipUnless(default_is_sf, "depends on Salesforce database.")
    def test_subquery_filter_on_child(self):
        """Filter with a Subquery() on a child object.

        Especially useful with ManyToMany field relationships.
        """
        associations = OpportunityContactRole.objects.filter(contact__email='a@example.com')
        soql = ("SELECT Opportunity.Name FROM Opportunity WHERE Opportunity.Id IN ("
                "SELECT OpportunityContactRole.OpportunityId FROM OpportunityContactRole "
                "WHERE OpportunityContactRole.Contact.Email = 'a@example.com')")
        qs = Opportunity.objects.filter(pk__in=associations.values('opportunity'))
        self.assertEqual(str(qs.values('name').query), soql)
        qs = Opportunity.objects.filter(pk__in=associations.values('opportunity_id'))
        self.assertEqual(str(qs.values('name').query), soql)
        qs = Opportunity.objects.filter(pk__in=Subquery(associations.values('opportunity')))
        self.assertEqual(str(qs.values('name').query), soql)

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

    @skipUnless(default_is_sf, "depends on Salesforce database.")
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


class SfParamsTest(TestCase):
    # type checking of this test case is currently not possible
    databases = '__all__'

    def test_params_handover_and_isolation(self):
        """Test that sp_params are propagated to the rest of the queryset chain
        but isolated from the previous part.
        """
        qs_1 = Contact.objects.all()
        qs_2 = qs_1.sf(query_all=True)
        qs_3 = qs_2.filter(first_name__gt='A')
        # a value is propagated to the next level, but not to the previous
        self.assertTrue(qs_3.query.sf_params.query_all)
        self.assertFalse(qs_1.query.sf_params.query_all)

    def test_minimal_aliases(self):
        """Test SOQL with minimal aliases without a table name of the main table"""
        # test that 'minimal_aliases' attribute is passed from qs to a salesforce compiler
        qs = Contact.objects.all()
        self.assertEqual(qs.query.get_compiler('salesforce').sf_params.minimal_aliases, False)
        self.assertEqual(qs.sf(minimal_aliases=True).query.get_compiler('salesforce').sf_params.minimal_aliases, True)

        # test that a normal SOQL is with table aliases
        qs = Contact.objects.filter(first_name='Peter').values('last_name')
        self.assertEqual(str(qs.query), "SELECT Contact.LastName FROM Contact WHERE Contact.FirstName = 'Peter'")

        # test that superfluous talbe aliases can be removed by 'minimal_aliases'
        expected_sql = "SELECT LastName FROM Contact WHERE FirstName = 'Peter'"
        qs = Contact.objects.sf(minimal_aliases=True).filter(first_name='Peter').values('last_name')
        self.assertEqual(str(qs.query), expected_sql)
        qs = Contact.objects.filter(first_name='Peter').sf(minimal_aliases=True).values('last_name')
        self.assertEqual(str(qs.query), expected_sql)
        qs = Contact.objects.filter(first_name='Peter').values('last_name').sf(minimal_aliases=True)
        self.assertEqual(str(qs.query), expected_sql)


class RegisterConversionTest(TestCase):
    @staticmethod
    def unregister_conversion(type_: Type) -> None:
        del driver.json_conversions[type_]
        del driver.sql_conversions[type_]
        if type_ in driver.subclass_conversions:
            driver.subclass_conversions.remove(type_)

    def test_arg_model_conversion(self) -> None:
        contact = Contact(last_name='test contact', pk='003001234567890AAA')

        self.assertNotIn(models.SalesforceModel, driver.json_conversions)
        self.assertNotIn(models.SalesforceModel, driver.sql_conversions)
        self.assertNotIn(models.SalesforceModel, driver.subclass_conversions)

        driver.register_conversion(models.SalesforceModel,
                                   json_conv=sobj_id,
                                   sql_conv=lambda x: driver.quoted_string_literal(sobj_id(x)),
                                   subclass=True)

        self.assertEqual(driver.arg_to_json(contact), contact.pk)
        self.assertEqual(driver.arg_to_soql(contact), contact.pk)

        self.assertIn(models.SalesforceModel, driver.json_conversions)
        self.assertIn(models.SalesforceModel, driver.sql_conversions)
        self.assertIn(models.SalesforceModel, driver.subclass_conversions)

        self.unregister_conversion(models.Model)

        self.assertNotIn(models.SalesforceModel, driver.json_conversions)
        self.assertNotIn(models.SalesforceModel, driver.sql_conversions)
        self.assertNotIn(models.SalesforceModel, driver.subclass_conversions)
