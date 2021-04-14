from typing import cast
import datetime
import decimal
import unittest
from django.test.utils import override_settings

from .models import Account, Contact, Unreal
from tests.test_mock.mocksf import MockJsonRequest, MockTestCase  # mock
from salesforce.dbapi.exceptions import SalesforceError


@override_settings(SF_MOCK_MODE='mixed')
class TestMock(MockTestCase):
    api_ver = '51.0'
    databases = {'salesforce'}

    @override_settings(SF_MOCK_MODE='record')
    # @override_settings(SF_MOCK_VERBOSITY=0)
    def test_simple_crud(self) -> None:
        acc = cast(Account, Account.objects.create(name='a'))
        acc = Account.objects.get(id=acc.id)
        acc.name = 'b'
        acc.save()
        acc.delete()

    @override_settings(SF_MOCK_MODE='playback')
    def test_defaulted_on_create(self) -> None:
        """Replay different types of data"""
        self.mock_add_expected(MockJsonRequest(
            "POST mock:///services/data/v51.0/sobjects/Unreal",
            {'IntX': '1', 'DecimalX': 3.333, 'DatetimeX': '2021-04-14T18:52:45.000+0000',
             'StrX': 'a', 'Normal': '', 'Str2X': 'b', 'DateX': '2021-04-14',
             'TimeX': '11:59:59.000000Z', 'FloatX': '3.14', 'BoolX': 'true'
             },
            resp='[{"errorCode":"NOT_FOUND","message":"The requested resource does not exist"}]',
            status_code=404)
        )
        with self.assertRaises(SalesforceError) as exc:
            _ = Unreal.objects.create(
                bool_x=True,
                int_x=1,
                float_x=3.14,
                decimal_x=decimal.Decimal('3.333'),
                str_x='a',
                date_x=datetime.date(2021, 4, 14),
                datetime_x=datetime.datetime(2021, 4, 14, 18, 52, 45).replace(tzinfo=datetime.timezone.utc),
                time_x=datetime.time(11, 59, 59),
                str2_x='b',
            )
        self.assertEqual(exc.exception.data,
                         [{'errorCode': 'NOT_FOUND', 'message': 'The requested resource does not exist'}])

    @override_settings(SF_MOCK_MODE='playback')
    def test_defaulted_on_create_implicit(self) -> None:
        """Replay an example that ends with an error"""
        self.mock_add_expected(MockJsonRequest(
            "POST mock:///services/data/v51.0/sobjects/Unreal",
            {'Normal': ''},
            resp='{"id":"003000000000123AAA","success":true,"errors":[]}',
            status_code=201)
        )
        obj = Unreal()
        obj.save()
        self.assertEqual(obj.pk, "003000000000123AAA")


class Test(unittest.TestCase):
    databases = {'salesforce'}

    def test(self) -> None:
        obj = Contact(last_name='a')
        obj.save()
        obj = Contact.objects.get(id=obj.id)
        # obj._state.__dict__.update({'db': 'salesforce', 'adding': False})
        obj.donor_class = None  # None can be saved to Salesforce, even if null=False
        obj.save()
