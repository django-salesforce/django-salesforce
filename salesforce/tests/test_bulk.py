"""Test of methods that can modify more records by one request
or can combine read and write and read to one request.
"""

from typing import List, Optional, Tuple
from django.conf import settings
from django.test import TestCase
from salesforce import SalesforceError
from salesforce.backend import DJANGO_22_PLUS
from salesforce.backend.test_helpers import skipUnless
from salesforce.testrunner.example.models import Campaign, CampaignMember, Contact


class BulkUpdateTest(TestCase):
    """The method queryset.bulk_update() is tested by a Contact with a unique custom field"""

    databases = '__all__'

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if not Contact.objects.update(vs=None) >= 9:
            Contact.objects.bulk_create([Contact(last_name='sf_test {}'.format(i)) for i in range(9)])

    @skipUnless(DJANGO_22_PLUS, "bulk_update() does not exist before Django 2.2.")
    @skipUnless(getattr(settings, 'SF_CUSTOM_INSTALLED', False), "requires Salesforce customization")
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        Contact.objects.update(vs=None)

    def test_bulk_update_normal(self) -> None:
        contacts = Contact.objects.all()[:9]
        for i, x in enumerate(contacts):
            x.vs = i
        Contact.objects.bulk_update(contacts, ['vs'])
        qs = Contact.objects.filter(vs__gte=0)
        self.assertEqual(sorted(qs.values_list('vs', flat=True)), [0, 1, 2, 3, 4, 5, 6, 7, 8])

    def common_bulk_update_error(self, expected_count: int, all_or_none: Optional[bool] = None) -> None:
        contacts = list(Contact.objects.all()[:9])
        for i, x in enumerate(contacts):
            x.vs = i
        contacts[6].vs = 5  # duplicate value 5
        with self.assertRaises(SalesforceError) as cm:
            Contact.objects.bulk_update(contacts, ['vs'], batch_size=4,  # type: ignore[call-arg] # all_or_none
                                        all_or_none=all_or_none)
        self.assertIn('Contact  DUPLICATE_VALUE', cm.exception.args[0])
        self.assertEqual(Contact.objects.exclude(vs=None).count(), expected_count)

    def test_bulk_update_error(self) -> None:
        """Verify that also valid data in the chunk after an error are updated"""
        self.common_bulk_update_error(expected_count=4 + 3 + 0)

    def test_bulk_update_error_all_or_none_true(self) -> None:
        """Verify that no data in the invalid chunk and after it are not updated"""
        self.common_bulk_update_error(expected_count=4 + 0 + 0, all_or_none=True)

    # def test_bulk_update_error_all_or_none_false(self) -> None:
    #     """Verify that all valid data are updated, even in batches after error"""
    #     self.common_bulk_update_error(expected_count=4 + 3 + 1, all_or_none=False)


class QuerysetUpdateTest(TestCase):
    """The method queryset.update() is tested by a Contact with a unique custom field"""

    databases = '__all__'

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        assert Contact.objects.update(vs=None) >= 2

    @skipUnless(getattr(settings, 'SF_CUSTOM_INSTALLED', False), "requires Salesforce customization")
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        Contact.objects.update(vs=None)

    def common_qs_update_error(self, expected_count: int, all_or_none: Optional[bool] = None) -> None:
        with self.assertRaises(SalesforceError) as cm:
            Contact.objects.sf(all_or_none=all_or_none).update(vs=1)  # type: ignore[attr-defined] # sf
        self.assertIn('Contact  DUPLICATE_VALUE', cm.exception.args[0])
        self.assertEqual(Contact.objects.filter(vs=1).count(), expected_count)

    def test_qs_update_error(self) -> None:
        """Verify that also valid data in the chunk after an error are updated"""
        self.common_qs_update_error(expected_count=1)

    def test_qs_update_error_all_or_none_true(self) -> None:
        """Verify that no data in the invalid chunk and after it are not updated"""
        self.common_qs_update_error(expected_count=0, all_or_none=True)

    # the parameter `all_or_none=False` can not be easily tested on Salesforce
    # (without special validation rules on Salesforce)


class BulkCreateTest(TestCase):
    """The method queryset.bulk_create() is tested by a CampaignMember"""

    databases = '__all__'
    contacts = []  # type: List[Contact]
    campaign = None  # type: Campaign

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.contacts = list(Contact.objects.filter(name__startswith='sf_test')[:2])
        campaigns = Campaign.objects.all()[:1]
        if campaigns:
            cls.campaign = campaigns[0]
        else:
            cls.campaign = Campaign.objects.create(name='test campaign')
        CampaignMember.objects.filter(campaign=cls.campaign, contact__in=cls.contacts).delete()

    def tearDown(self) -> None:
        CampaignMember.objects.filter(campaign=self.campaign, contact__in=self.contacts).delete()

    def common_bulk_create_error(self, expected: Tuple[int, int, int], all_or_none: Optional[bool] = None) -> None:
        expect_errors, expect_rollbacks, expect_success = expected
        members = [
            CampaignMember(campaign=self.campaign, contact=self.contacts[i], status='Sent')
            for i in range(2)
            for _ in range(3)
        ]
        qs = CampaignMember.objects.all()
        if all_or_none is not None:
            qs = qs.sf(all_or_none=all_or_none)  # type: ignore[attr-defined] # noqa # sf
        with self.assertRaises(SalesforceError) as cm:
            qs.bulk_create(members, batch_size=3)
        error_summary = [x.strip() for x in cm.exception.args[0].split('\n') if 'Error Summary' in x][0]
        expected_summary = 'Error Summary: errors={}, rollback/cancel={}, success={}'.format(
            expect_errors, expect_rollbacks, expect_success)
        self.assertEqual(error_summary, expected_summary)
        self.assertIn('CampaignMember  DUPLICATE_VALUE', cm.exception.args[0])
        qs = CampaignMember.objects.filter(campaign=self.campaign, contact__in=self.contacts)
        self.assertEqual(qs.count(), expect_success)

    def test_bulk_create_error(self) -> None:
        """Verify that also valid data in the chunk after an error are inserted"""
        self.common_bulk_create_error(expected=(2, 0, 1))

    def test_bulk_create_error_all_or_none_true(self) -> None:
        """Verify that no data in the invalid chunk and after it are not inserted"""
        self.common_bulk_create_error(expected=(2, 1, 0), all_or_none=True)

    # def test_bulk_create_error_all_or_none_false(self) -> None:
    #     """Verify that all valid data are inserted, even in batches after error"""
    #     self.common_bulk_create_error(expected=(2, 0, 1), all_or_none=False)
