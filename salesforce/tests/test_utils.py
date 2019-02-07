"""
Tests for `salesforce.utils`
"""
# pylint:disable=protected-access

from unittest import skipUnless

from django.test import TestCase

from salesforce.dbapi.driver import beatbox
from salesforce.testrunner.example.models import Account, Lead
from salesforce.utils import convert_lead


class UtilitiesTest(TestCase):
    databases = '__all__'

    @skipUnless(beatbox, "Beatbox needs to be installed in order to run this test.")
    def test_lead_conversion(self):
        """
        Create a Lead object within Salesforce and try to
        convert it, convert/merge it with the information from a duplicit Lead,
        then clean all the generated objects.
        """
        lead = Lead(FirstName="Foo", LastName="Bar", Company="django-salesforce",
                    Street='Test Avenue 45')
        lead.save()
        lead2 = Lead(FirstName="Foo", LastName="Bar", Company="django-salesforce",
                     Phone='123456789')
        lead2.save()
        ret = None
        try:
            # convert the first Lead
            ret = convert_lead(lead, doNotCreateOpportunity=True)
            # print("Response from convertLead: " +
            #       ', '.join('%s: %s' % (k, v) for k, v in sorted(ret.items())))
            expected_names = set(('accountId', 'contactId', 'leadId', 'opportunityId', 'success'))
            self.assertEqual(set(ret), expected_names)
            self.assertEqual(ret['success'], 'true')
            # merge the new Account with the second Lead
            ret2 = convert_lead(lead2, doNotCreateOpportunity=True, accountId=ret['accountId'])
            account = Account.objects.get(pk=ret['accountId'])
            # verify that account is merged
            self.assertEqual(ret2['accountId'], account.pk)
            self.assertEqual(account.BillingStreet, 'Test Avenue 45')
            self.assertEqual(account.Phone, '123456789')
        finally:
            # Cleaning up...
            if ret:
                # Deleting the Account object will also delete the related Contact
                # and Opportunity objects.
                try:
                    account = Account.objects.get(pk=ret['accountId'])
                except Exception:  # pylint:disable=broad-except
                    # this allows to recycle the account even if the queryset code is broken
                    account = Account(pk=ret['accountId'])
                    account._state.db = lead._state.db
                account.delete()
            lead.delete()   # FYI, ret['leadId'] == lead.pk
            lead2.delete()
