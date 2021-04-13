from typing import cast
import datetime
import decimal
import unittest
from django.db import connections
from django.test.utils import override_settings

from .models import Unreal, Account, Contact
from tests.test_mock.mocksf import MockTestCase  # mock, MockJsonRequest,
from salesforce.dbapi.exceptions import SalesforceError


@override_settings(SF_MOCK_MODE='mixed')
class TestMock(MockTestCase):
    api_ver = '48.0'
    databases = {'salesforce'}

    def setUp(self) -> None:
        connections['salesforce'].connect()
        super().setUp()

    @override_settings(SF_MOCK_MODE='record')
    def test_defaulted_on_create(self) -> None:
        acc = cast(Account, Account.objects.create(name='a'))
        acc = Account.objects.get(id=acc.id)
        print(acc.owner.name)
        acc.delete()
        try:
            obj = Unreal.objects.create(
                bool_x=True,
                int_x=1,
                float_x=3.14,
                decimal_x=decimal.Decimal('3.333'),
                str_x='a',
                date_x=datetime.date.today(),
                datetime_x=datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc),
                time_x=datetime.time(11, 59, 59),
                str2_x='b',
            )
        except SalesforceError:
            pass
        try:
            obj = Unreal()
            obj.save()
            print(Unreal.objects.get(id=obj.id).__dict__)
        except SalesforceError:
            pass
        bool(obj)


class Test(unittest.TestCase):
    databases = {'salesforce'}

    def test(self) -> None:
        obj = Contact(last_name='a')
        obj.save()
        obj = Contact.objects.get(id=obj.id)
        # obj._state.__dict__.update({'db': 'salesforce', 'adding': False})
        obj.donor_class = None
        obj.save()
        print(Contact.objects.get(id=obj.id).__dict__)
