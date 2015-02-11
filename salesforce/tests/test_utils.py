from django.test import TestCase
from django.core.exceptions import ObjectDoesNotExist
import unittest


from salesforce.testrunner.example.models import Account, Contact, Lead, Opportunity
from salesforce.utils import convert_lead

try:
    import beatbox
except ImportError:
    beatbox = None


class UtilitiesTest(TestCase):

    @unittest.skipUnless(beatbox, "Beatbox needs to be installed in order to run this test.")
    def test_lead_conversion(self):
        """
        Create a Lead object within Salesforce and try to
        convert it, then clean all the generated objects.
        """
        lead = Lead(FirstName="Foo", LastName="Bar", Company="django-salesforce")
        lead.save()
        r = convert_lead(lead)
        print("Response from convertLead: " + str(r))
        print("Account ID: " + str(r[0]))
        print("Contact ID: " + str(r[1]))
        print("Opportunity ID: " + str(r[3]))

        # Cleaning up...
        # Deleting the Account object will also delete the related Contact
        # and Opportunity objects.
        account = Account.objects.get(pk=str(r[0]))
        account.delete()
        
        lead.delete()   # FYI, r[2] == lead.pk