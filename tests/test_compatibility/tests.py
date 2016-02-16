"""Backward compatible behaviour with primary key 'Id'."""
from __future__ import absolute_import
from django.test import TestCase
from tests.test_compatibility.models import Lead, User
from salesforce.backend.test_helpers import current_user, uid


class CompatibilityTest(TestCase):
    def test_capitalized_id(self):
        test_lead = Lead(Company='sf_test lead' + uid, LastName='name')
        test_lead.save()
        try:
            refreshed_lead = Lead.objects.get(Id=test_lead.Id)
            self.assertEqual(refreshed_lead.Id, test_lead.Id)
            self.assertEqual(refreshed_lead.Owner.Username, current_user)
            leads = Lead.objects.filter(Company='sf_test lead' + uid, LastName='name')
            self.assertGreaterEqual(len(leads), 1)
            repr(test_lead.__dict__)
        finally:
            test_lead.delete()


class DjangoCompatibility(TestCase):
    def test_autofield_compatible(self):
        """Test that the light weigh AutoField is compatible in all Django ver."""
        primary_key = [x for x in Lead._meta.fields if x.primary_key][0]
        self.assertEqual(primary_key.auto_created, True)
        self.assertEqual(primary_key.get_internal_type(), 'AutoField')
        self.assertIn(primary_key.name, ('id', 'Id'))
