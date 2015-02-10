from django.test import TestCase

from salesforce.testrunner.example.models import Lead
from salesforce.utils import convert_lead


class UtilitiesTest(TestCase):

    def test_lead_conversion(self):
        """
        Create a Lead object within Salesforce and try to
        convert it.
        """
        lead = Lead(FirstName="Foo", LastName="Bar", Company="django-salesforce")
        lead.save()
        r = convert_lead(lead)
        print("Response from convertLead: " + str(r))
