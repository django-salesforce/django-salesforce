"""
Tests that do not need to connect servers
"""

from django.test import TestCase
from django.db.models import DO_NOTHING
from salesforce import fields, models
from salesforce.testrunner.example.models import (Contact, Opportunity,
		OpportunityContactRole, ChargentOrder)

from salesforce.backend.subselect import TestSubSelectSearch
import salesforce

class EasyCharField(models.CharField):
	def __init__(self, max_length=255, null=True, default='', **kwargs):
		return super(EasyCharField, self).__init__(max_length=max_length, null=null, default=default, **kwargs)


class EasyForeignKey(models.ForeignKey):
	def __init__(self, othermodel, on_delete=DO_NOTHING, **kwargs):
		return super(EasyForeignKey, self).__init__(othermodel, on_delete=on_delete, **kwargs)


class TestField(TestCase):
	"""
	Unit tests for salesforce.fields that don't need to connect Salesforce.
	"""
	def test_auto_db_column(self):
		"""
		Verify that db_column is not important in most cases, but it has
		precedence if it is specified.
		Verify it for lower_case and CamelCase conventions, for standard fields
		and for custom fields, for normal fields and for foreign keys.
		"""
		class Aa(models.SalesforceModel):
			pass
		class Dest(models.SalesforceModel):
			pass
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
		test(EasyForeignKey(Aa, name='MyCustomForeignField', custom=True), 'MyCustomForeignFieldId', 'MyCustomForeignField__c')
		test(EasyForeignKey(Aa, name='my_custom_foreign_field', custom=True), 'my_custom_foreign_field_id', 'MyCustomForeignField__c')


class TestQueryCompiler(TestCase):
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
		qs = OpportunityContactRole.objects.filter(role='abc',
				opportunity__in=Opportunity.objects.filter(stage='Prospecting'))
		sql, params = qs.query.get_compiler('salesforce').as_sql()
		self.assertRegexpMatches(sql, "WHERE Opportunity.StageName =",
					"Probably because aliases are invalid for SFDC, e.g. 'U0.StageName'")
		self.assertRegexpMatches(sql, 'SELECT .*OpportunityContactRole\.Role.* '
										'FROM OpportunityContactRole WHERE \(.* AND .*\)')
		self.assertRegexpMatches(sql, 'OpportunityContactRole.OpportunityId IN '
					'\(SELECT Opportunity\.Id FROM Opportunity WHERE Opportunity\.StageName = %s ?\)')
		self.assertRegexpMatches(sql, 'OpportunityContactRole.Role = %s')

	def test_none_method_queryset(self):
		"""Test that none() method in the queryset returns [], not error"""
		request_count_0 = salesforce.backend.query.request_count
		self.assertEqual(tuple(Contact.objects.none()), ())
		self.assertEqual(tuple(Contact.objects.all().none().all()), ())
		self.assertEqual(repr(Contact.objects.none()), '[]')
		self.assertEqual(salesforce.backend.query.request_count, request_count_0,
				"Do database requests should be done with .none() method")
