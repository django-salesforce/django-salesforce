"""Test djangoBackward compatible behaviour with primary key 'Id'."""
from __future__ import absolute_import
from django.test import TestCase

from .models import Account, Contact


class DefaultDbTest(TestCase):
    databases = '__all__'

    def test_simple_create(self):
        """Test create new salesforce objects in a default db."""
        test_account = Account.objects.create(name='sf_test account')
        test_contact = Contact.objects.create(last_name='sf_test_contact', account=test_account)
        try:
            self.assertEqual(Account.objects.filter(name='sf_test account').count(), 1)
            self.assertEqual(Contact.objects.filter(account__name='sf_test account').count(), 1)
        finally:
            test_contact.delete()
            test_account.delete()
