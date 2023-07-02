from django.db import connections
from django.test.utils import override_settings
from tests.test_mock.mocksf import MockTestCase
from salesforce.testrunner.example.models import Contact


@override_settings(SF_MOCK_MODE='mixed')
@override_settings(SF_MOCK_VERBOSITY=0)
class TestMock(MockTestCase):
    api_ver = '48.0'
    databases = {'salesforce'}

    def setUp(self) -> None:
        connections['salesforce'].connect()
        super().setUp()

    @override_settings(SF_MOCK_MODE='record')
    def test(self):
        from django.db import connections
        list(Contact.objects.filter(first_name__startswith='sf_test'))
        cur = connections['salesforce'].cursor()
        cur.execute(
            'SELECT Contact.Id, Contact.AccountId, Contact.LastName, Contact.FirstName, Contact.Name, '
            'Contact.Email, Contact.EmailBouncedDate, Contact.OwnerId FROM Contact WHERE '
            '(Contact.FirstName LIKE %s OR Contact.LastName LIKE %s)', ('sf_test%', 'sf_test%')
        )
