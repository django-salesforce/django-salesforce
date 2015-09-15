"""
Tests for `salesforce.utils`
"""
from django.test import TestCase
import unittest


from salesforce.testrunner.example.models import Account, Contact, Lead, Opportunity
from salesforce.utils import convert_lead
from ..backend.test_helpers import skip, skipUnless

try:
    import beatbox
except ImportError:
    beatbox = None


class UtilitiesTest(TestCase):

    @skipUnless(beatbox, "Beatbox needs to be installed in order to run this test.")
    def test_lead_conversion(self):
        """
        Create a Lead object within Salesforce and try to
        convert it, then clean all the generated objects.
        """
        lead = Lead(FirstName="Foo", LastName="Bar", Company="django-salesforce")
        lead.save()
        ret = None
        try:
            ret = convert_lead(lead)
            print("Response from convertLead: " +
                    ', '.join('%s: %s' % (k, v) for k, v in sorted(ret.items())))
            expected_names = set(('accountId', 'contactId', 'leadId', 'opportunityId', 'success'))
            self.assertEqual(set(ret), expected_names)
            self.assertEqual(ret['success'], 'true')
        finally:
            # Cleaning up...
            if ret:
                # Deleting the Account object will also delete the related Contact
                # and Opportunity objects.
                account = Account.objects.get(pk=ret['accountId'])
                account.delete()
            lead.delete()   # FYI, ret['leadId'] == lead.pk
