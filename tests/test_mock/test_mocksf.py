"""
Test that MockTestCase works in all modes, including "record"
(this must connect to servers)
"""
from django.db import connections
from django.test.utils import override_settings

from salesforce.backend.test_helpers import sf_alias
from tests.test_mock.mocksf import mock, MockJsonRequest, MockTestCase


@override_settings(SF_MOCK_MODE='mixed')
class TestMock(MockTestCase):
    api_version = '39.0'

    def prepare_expected(self):
        self.mock_add_expected(MockJsonRequest(
            'GET mock:///services/data/v39.0/query/?q=SELECT+Name+FROM+Contact+LIMIT+1',
            resp=('{"totalSize": 1, "done": true, "records": [{'
                  '  "attributes": {"type": "Contact",'
                  '                 "url": "/services/data/v39.0/sobjects/Contact/003A000000wJICkIAO"},'
                  '  "Name": "django-salesforce test"}]}')
        ))

    @override_settings(SF_MOCK_MODE='playback')
    def test_mock_playback(self):
        self.prepare_expected()
        # test
        cur = connections[sf_alias].cursor()
        with mock.patch.object(cur.cursor.connection, '_api_version', '39.0'):
            cur.execute("SELECT Name FROM Contact LIMIT 1")
        self.assertEqual(list(cur.fetchall()), [['django-salesforce test']])

    def test_mock_unused_playback(self):
        # pylint:disable=deprecated-method,protected-access
        self.prepare_expected()
        self.assertRaisesRegexp(AssertionError, "Not all expected requests has been used", self.tearDown)
        connections[sf_alias].connection._sf_session.index += 1  # mock a consumed request

    @override_settings(SF_MOCK_MODE='record')
    @override_settings(SF_MOCK_VERBOSITY=0)
    def test_mock_record(self):
        # test
        cur = connections[sf_alias].cursor()
        cur.execute("SELECT Name FROM Contact LIMIT 1")
        row, = cur.fetchall()
        self.assertEqual(len(row), 1)
        self.assertIsInstance(row[0], str)

    @override_settings(SF_MOCK_MODE='playback')
    def test_response_parser(self):
        "Test a response parser by a Mock playback, without testing the request."
        cur = connections[sf_alias].cursor()
        req = MockJsonRequest(
            "POST mock:///services/data/v20.0/xyz",
            request_json='{"a":[123]}',
            resp="""{
                "a":3
                ...
            }""", check_request=False)
        self.mock_add_expected(req)
        ret = cur.handle_api_exceptions('POST', 'mock:///services/data/')
        self.assertEqual(ret.json()['a'], 3)
