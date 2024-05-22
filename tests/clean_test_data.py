"""
Clean test objects after an interrupted test.

All tests are written so that a failed test should usually not leave database objects,
but a test interrupted by debugger or Ctrl-C could do it.
"""
from typing import List
from unittest import TestCase
from django.db.models import Q
from salesforce.backend.operations import BULK_BATCH_SIZE
from salesforce.backend.query import SalesforceQuerySet
from salesforce.testrunner.example.models import (Account, Campaign, Contact, Lead, Opportunity, Product, Test,
                                                  ContentDocument)
from salesforce.tests.test_integration import sf_tables


def qs_delete(qs: SalesforceQuerySet) -> List[int]:
    """Delete all items of queryset"""
    ret = list(qs)
    s = 0
    for offs in range(0, len(ret), BULK_BATCH_SIZE):
        ids = [x.pk for x in ret[offs: offs + BULK_BATCH_SIZE]]
        s += qs.model.objects.filter(pk__in=ids).delete()[0]
    return [s]


class CleanTests(TestCase):

    def setUp(self):
        ret = [
            qs_delete(Account.objects.filter(
                Q(Name__startswith='sf_test') | Q(Name__startswith='test') |
                Q(Name__in=[r"""Dr. Evil's Giant\' "Laser", LLC""", "IntegrationTest Account"])
            )),
            qs_delete(Campaign.objects.filter(name__startswith='test ')),
            qs_delete(Contact.objects.filter(Q(first_name__startswith='sf_test') | Q(last_name__startswith='sf_test') |
                                             Q(name='Joe Freelancer'))),
            qs_delete(Lead.objects.filter(LastName__startswith='UnitTest')),
            qs_delete(Opportunity.objects.filter(name__in=('test op', 'Example Opportunity'))),
            qs_delete(Product.objects.filter(Name__startswith='test ')),
            qs_delete(ContentDocument.objects.filter(title='some file.txt')),
        ]
        if 'django_Test__c' in sf_tables():
            ret.append(qs_delete(Test.objects.all()))
        print("Deleted objects={}".format(sum(x[0] for x in ret)))

    def test_clean_all_test_data(self):
        """It is cleaninng all known test data that can be necessary sometimes after interrupted tests
        e.g. after debugging.
        It is not a test and it is not selected with automatic tests
        """
        pass
