from __future__ import absolute_import
from django.conf import settings
from django.test import TestCase
from salesforce.backend import sf_alias
from tests.test_mixin.models import Account, Contact, User, ProxyContact, Proxy2Contact

current_user = settings.DATABASES[sf_alias]['USER']


def refresh(obj):
	"""
	Get the same object refreshed from the same db.
	"""
	db = obj._state.db
	return type(obj).objects.using(db).get(pk=obj.pk)


class MixinTest(TestCase):
	def test_mixin(self):
		"""Test that mixins from abstract classes work and also proxy models."""
		# create the object with one field from the second ancestor and one from the first
		test_account = Account(name='sf_test account', description='experimental')
		test_account.save()
		test_account = refresh(test_account)
		test_contact = Contact(first_name='sf_test', last_name='my', account=test_account)
		test_contact.save()
		try:
			test_contact = refresh(test_contact)
			# verify foreign keys to and from the complicated model
			self.assertEqual(test_contact.account.owner.username, current_user)
			contacts = Contact.objects.filter(account__name='sf_test account')  # description='experimental')
			self.assertEqual(len(contacts), 1)
			repr(test_contact.__dict__)
			repr(test_account.__dict__)
			# Verify that a proxy model correctly recognizes the db_table from
			# a concrete model by two levels deeper.
			self.assertEqual(Proxy2Contact.objects.get(pk=test_contact.pk).pk, test_contact.pk)
		finally:
			test_contact.delete()
			test_account.delete()
