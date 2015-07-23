"""
Tests that do not need to connect servers
"""

from django.test import TestCase
from django.db.models import DO_NOTHING
from salesforce import fields, models

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
