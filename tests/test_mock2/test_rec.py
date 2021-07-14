"""Recorded tests by MockTestCase"""
from typing import cast
import datetime
import decimal
import unittest
import django
from django.db import connections
from django.test.utils import override_settings

from .models import Account, Contact, Unreal
from tests.test_mock.mocksf import MockJsonRequest, MockRequest, MockTestCase  # mock
from salesforce.backend import DJANGO_30_PLUS
from salesforce.dbapi.exceptions import SalesforceError


@override_settings(SF_MOCK_MODE='mixed')
class TestMock(MockTestCase):
    api_version = '51.0'
    databases = {'salesforce'}

    @override_settings(SF_MOCK_MODE='record')
    @override_settings(SF_MOCK_VERBOSITY=0)
    def test_simple_crud(self) -> None:
        """Record the commands to a variable (quiet verbosity)"""
        acc = cast(Account, Account.objects.create(name='a'))
        acc = Account.objects.get(id=acc.id)
        acc.name = 'b'
        acc.save()
        acc.delete()
        output = django.db.connections['salesforce'].connection._sf_session.mock_recorded
        self.assertIn('POST mock:///services/data/', output[0])
        self.assertIn('GET mock:///services/data/', output[1])
        self.assertIn('PATCH mock:///services/data/', output[2])
        self.assertIn('DELETE mock:///services/data/', output[3])

    @override_settings(SF_MOCK_MODE='playback')
    def test_simple_crud_replay(self) -> None:
        """Replay the recorded commands and verify that also requests are exactly repeated"""
        optional_sql = '+LIMIT+21' if DJANGO_30_PLUS else ''
        self.mock_add_expected([
            MockJsonRequest(
                "POST mock:///services/data/v51.0/sobjects/Account",
                req={'Name': 'a'},
                resp='{"id":"001M000001FgVKlIAN","success":true,"errors":[]}',
                status_code=201),
            MockJsonRequest(
                "GET mock:///services/data/v51.0/query/?q=SELECT+Account.Id%2C+Account.Name%2C+Account.OwnerId+"
                "FROM+Account+WHERE+Account.Id+%3D+%27001M000001FgVKlIAN%27" + optional_sql,
                resp='{"totalSize":1,"done":true,"records":['
                '{"attributes":{"type":"Account","url":"/services/data/v51.0/sobjects/Account/001M000001FgVKlIAN"},'
                '"Id":"001M000001FgVKlIAN","Name":"a","OwnerId":"005M0000007whduIAA"}]}'),
            MockJsonRequest(
                "PATCH mock:///services/data/v51.0/sobjects/Account/001M000001FgVKlIAN",
                req={'Name': 'b', 'OwnerId': '005M0000007whduIAA'},
                request_type='',
                status_code=204),
            MockRequest(
                "DELETE mock:///services/data/v51.0/sobjects/Account/001M000001FgVKlIAN",
                request_type='',
                status_code=204)
        ])

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

    def is_complete(self) -> bool:
        cur = connections['salesforce'].cursor()
        cur.execute("select QualifiedApiName from FieldDefinition "
                    "where EntityDefinition.QualifiedApiName = 'Contact' "
                    "and QualifiedApiName='Donor_class__c'")
        return bool(len(cur.fetchall()))

    def test(self) -> None:
        if not self.is_complete():
            self.skipTest("Not found custom field 'Donor_class__c'")

        obj = Contact(last_name='a')
        obj.save()
        obj = Contact.objects.get(id=obj.id)
        # obj._state.__dict__.update({'db': 'salesforce', 'adding': False})
        obj.donor_class = None  # None can be saved to Salesforce, even if null=False
        obj.save()
        obj.delete()
