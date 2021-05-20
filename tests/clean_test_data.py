"""
Clean test objects after an interrupted test.

All tests are written so that a failed test should usually not leave database objects,
but a test interrupted by debugger or Ctrl-C could do it.
"""
from unittest import TestCase
from django.db.models import Q
from salesforce.testrunner.example.models import Account, Campaign, Contact, Lead, Opportunity, Product, Test
from salesforce.tests.test_integration import sf_tables


class CleanTests(TestCase):

    def setUp(self):
        ret = [
            Account.objects.filter(
                Q(Name__startswith='sf_test') | Q(Name__startswith='test') |
                Q(Name__in=[r"""Dr. Evil's Giant\' "Laser", LLC""", "IntegrationTest Account"])
            ).delete(),
            Campaign.objects.filter(name__startswith='test ').delete(),
            Contact.objects.filter(Q(first_name__startswith='sf_test') | Q(last_name__startswith='sf_test') |
                                   Q(name='Joe Freelancer')).delete(),
            Lead.objects.filter(LastName__startswith='UnitTest').delete(),
            Opportunity.objects.filter(name__in=('test op', 'Example Opportunity')).delete(),
            Product.objects.filter(Name__startswith='test ').delete(),
        ]
        if 'django_Test__c' not in sf_tables():
            ret.append(Test.objects.filter(test_text='sf_test').delete())
        print("Deleted objects={}".format(sum(x[0] for x in ret)))

    def test_clean_all_test_data(self):
        """It is cleaninng all known test data that can be necessary sometimes after interrupted tests
        e.g. after debugging.
        It is not a test and it is not selected with automatic tests
        """
        pass
