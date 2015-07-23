from django.test import TestCase
from django.db import connections
import unittest


from salesforce.testrunner.example.models import Account, Contact, Lead, Opportunity
from salesforce.utils import convert_lead

try:
	from unittest import skip, skipUnless
except ImportError:
	# old Python 2.6 (Django 1.4 - 1.6 simulated unittest2)
	from django.utils.unittest import skip, skipUnless
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

        # Get a status name setting for converted Leads
        cur = connections['salesforce'].cursor()
        cur.execute("SELECT MasterLabel FROM LeadStatus WHERE IsConverted=true")
        converted_status = cur.fetchone()['MasterLabel']

        ret = convert_lead(lead, converted_status=converted_status)
        print("Response from convertLead: " +
                ', '.join('%s: %s' % (k, v) for k, v in sorted(ret.items())))
        expected_names = set(('accountId', 'contactId', 'leadId', 'opportunityId', 'success'))
        self.assertEqual(set(ret), expected_names)
        self.assertEqual(ret['success'], 'true')

        # Cleaning up...
        # Deleting the Account object will also delete the related Contact
        # and Opportunity objects.
        account = Account.objects.get(pk=ret['accountId'])
        account.delete()

        lead.delete()   # FYI, ret['leadId'] == lead.pk
