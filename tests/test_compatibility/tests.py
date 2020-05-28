"""Backward compatible behaviour with primary key 'Id'."""
from django.test import TestCase
from tests.test_compatibility.models import Lead, B, AtoB
from salesforce.backend.test_helpers import current_user, uid_version as uid


class CompatibilityTest(TestCase):
    databases = '__all__'

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
    databases = '__all__'

    def test_autofield_compatible(self):
        """Test that the light weigh AutoField is compatible in all Django ver."""
        primary_key = [x for x in Lead._meta.fields if x.primary_key][0]
        self.assertEqual(primary_key.auto_created, True)
        self.assertEqual(primary_key.get_internal_type(), 'AutoField')
        self.assertIn(primary_key.name, ('id', 'Id'))


class ManyToManyTest(TestCase):

    def test_subquery_filter_on_child(self):
        """Filter with a Subquery() on a child object.

        Especially useful with ManyToMany field relationships.
        """
        assoc = AtoB.objects.filter(a__email='a@example.com')
        qs = B.objects.filter(pk__in=assoc.values('b'))
        soql = (
            "SELECT B__c.Id FROM B__c WHERE B__c.Id IN ("
            "SELECT AtoB__c.B__c FROM AtoB__c WHERE AtoB__c.A__r.Email__c = 'a@example.com'"
            ")"
        )
        self.assertEqual(str(qs.query), soql)
