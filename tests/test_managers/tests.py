"""Test djangoBackward compatible behaviour with primary key 'Id'."""
from django.test import TestCase

from .models import Account, Contact
from salesforce.backend.test_helpers import LazyTestMixin


class CompatibilityTest(TestCase, LazyTestMixin):
    databases = {'salesforce'}

    def test_alternate_default_manager(self) -> None:
        """Test an alternate default manager with a queryset"""
        test_acc = Account.objects.create(name='Aa')
        test_cnt = Contact.objects.create(last_name='B', account=test_acc)
        try:
            # test that only one request is used for .save()
            with self.lazy_assert_n_requests(1):
                test_cnt.save()

            # test again that only one request is used for .save() for a combined queryset
            wrk = Contact.objects.filter(last_name='B')
            tmp = wrk[0]
            tmp.last_name = 'C'
            with self.lazy_assert_n_requests(1):
                tmp.save()

            # check that the default queryset is not empty
            _ = Contact.objects.all()[0]

            with self.lazy_assert_n_requests(2):
                Contact.objects.sf(edge_updates=True).update(last_name='sf_test')

            self.lazy_check()
        finally:
            test_cnt.delete()
            test_acc.delete()
