"""Test djangoBackward compatible behaviour with primary key 'Id'."""
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

    def test_using_salesforce_after_default(self):
        """Test with .using('salesforce') after 'default' database queryset."""
        self.assertGreater(Contact.objects.using('salesforce').count(), 1)
        self.assertGreater(Contact.objects.all().using('salesforce').count(), 1)

    def test_using_salesforce_from_default(self):
        """Test by saving a single object save (also copy)."""
        test_account_orig = Account(name='sf_test account 0')
        test_account_orig.save(using='salesforce')
        try:
            test_account_orig.save(using='default')
            test_account_orig.save(using='salesforce')
            test_account = Account.objects.get(pk=test_account_orig.pk)
            # update salesforce
            test_account_orig.name = 'sf_test account 1'
            test_account_orig.save(using='salesforce')
            self.assertEqual(Account.objects.using('salesforce').filter(name='sf_test account 1').count(), 1)

        finally:
            test_account_orig.delete()

        # update using=default
        test_account.name = 'sf_test account 2'
        test_account.save(using='default')
        self.assertEqual(Account.objects.using('default').filter(name='sf_test account 2').count(), 1)

        # update without using
        test_account.name = 'sf_test account 3'
        test_account.save()
        self.assertEqual(Account.objects.using('default').filter(name='sf_test account 3').count(), 1)

    def test_q(self):
        test_account = Account(name='sf_test account', pk=None)
        test_account.save(using='default')
        test_account.save()  # re-save

    def test_bulk_create_alt(self):
        """Test bulk create on an alternate database"""
        # bulk_create an alternate
        objs = Account.objects.bulk_create([Account(name='sf_test account 4') for x in range(2)])
        self.assertEqual(len(objs), 2)
        test_account_qs = Account.objects.filter(name='sf_test account 4')
        self.assertEqual(test_account_qs.count(), 2)
        test_account_qs.delete()
        self.assertEqual(test_account_qs.count(), 0)

    # TODO test also bulk_create copy with  SALESFORCE_DB_ALIAS = 'salesforce'

    def test_update_delete_on_qs(self):
        """Combined tests on a default database, update and delete on a queryset"""
        test_account = Account.objects.create(name='sf_test account 0')

        # update single
        test_account.name = 'sf_test account'
        test_account.save()
        self.assertEqual(Account.objects.filter(name='sf_test account').count(), 1)

        # create with a ForeignKey and search related
        Contact.objects.create(last_name='sf_test contact', account=test_account)
        self.assertEqual(Contact.objects.filter(account__name='sf_test account').count(), 1)

        # update on queryset
        cnt = (Contact.objects.filter(account__name='sf_test account')
               .update(last_name='sf_test contact 2'))
        self.assertEqual(cnt, 1)
        self.assertEqual(Contact.objects.filter(last_name='sf_test contact 2').count(), 1)
