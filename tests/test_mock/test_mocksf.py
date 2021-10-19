"""
Test that MockTestCase works in all modes, including "record"
(this must connect to servers)
"""
import unittest
from typing import List, Optional
from django.db import connections
from django.test.utils import override_settings

from salesforce.backend.test_helpers import sf_alias
from tests.test_mock.mocksf import (mock, MockJsonRequest, MockTestCase,
                                    case_safe_sf_id, check_sf_api_id, extract_ids)


@override_settings(SF_MOCK_MODE='mixed')
class TestMock(MockTestCase):
    api_version = '39.0'

    def prepare_expected(self) -> None:
        self.mock_add_expected(MockJsonRequest(
            'GET mock:///services/data/v39.0/query/?q=SELECT+Name+FROM+Contact+LIMIT+1',
            resp=('{"totalSize": 1, "done": true, "records": [{'
                  '  "attributes": {"type": "Contact",'
                  '                 "url": "/services/data/v39.0/sobjects/Contact/003A000000wJICkIAO"},'
                  '  "Name": "django-salesforce test"}]}')
        ))

    @override_settings(SF_MOCK_MODE='playback')
    def test_mock_playback(self) -> None:
        self.prepare_expected()
        # test
        cur = connections[sf_alias].cursor()
        with mock.patch.object(cur.cursor.connection, '_api_version', '39.0'):
            cur.execute("SELECT Name FROM Contact LIMIT 1")
        self.assertEqual(list(cur.fetchall()), [('django-salesforce test',)])

    def test_mock_unused_playback(self) -> None:
        self.prepare_expected()
        # warning: tearDown() will be called 2x (here + autopmatic), that could cause side effects
        self.assertRaisesRegex(AssertionError, "Not all expected requests has been used", self.tearDown)

    @override_settings(SF_MOCK_MODE='record')
    @override_settings(SF_MOCK_VERBOSITY=0)
    def test_mock_record(self) -> None:
        # test
        cur = connections[sf_alias].cursor()
        cur.execute("SELECT Name FROM Contact LIMIT 1")
        row, = cur.fetchall()
        self.assertEqual(len(row), 1)
        self.assertIsInstance(row[0], str)

    @override_settings(SF_MOCK_MODE='playback')
    def test_response_parser(self) -> None:
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


class SafeIdTest(unittest.TestCase):
    def test_case_safe_sf_id(self) -> None:
        self.assertEqual(case_safe_sf_id('000000000000000AAA'), '000000000000000AAA')
        self.assertEqual(case_safe_sf_id('000000000000000'), '000000000000000AAA')
        self.assertEqual(case_safe_sf_id('A00000000000000'), 'A00000000000000BAA')
        self.assertEqual(case_safe_sf_id(None), None)
        self.assertRaises(TypeError, case_safe_sf_id, '000000000000000AAB')
        self.assertRaises(TypeError, case_safe_sf_id, '00000000000000@')
        self.assertRaises(TypeError, case_safe_sf_id, '000000000000')

    def test_check_sf_api_id(self) -> None:
        self.assertEqual(check_sf_api_id('000000000000000'), '000000000000000AAA')
        self.assertEqual(check_sf_api_id('0'), None)

    def test_extract_ids(self) -> None:
        def extract(data: str, data_type: Optional[str] = None) -> List[str]:
            return [x[0] for x in extract_ids(data, data_type)]
        json_demo = '{"key": "000000000000000AAA", "name": "something"}'
        soap_demo = '<key>000000000000000AAA</key><name>something</name>'
        soql_demo = "WHERE key = '000000000000000AAA' AND name = 'something'"

        self.assertEqual(extract(json_demo), ['000000000000000AAA'])
        self.assertEqual(extract(soap_demo), ['000000000000000AAA'])
        self.assertEqual(extract(soql_demo), ['000000000000000AAA'])

        self.assertEqual(extract(json_demo, 'rest'), ['000000000000000AAA'])
        self.assertEqual(extract(soap_demo, 'rest'), [])
        self.assertEqual(extract(soql_demo, 'rest'), [])

        self.assertEqual(extract(json_demo, 'soap'), [])
        self.assertEqual(extract(soap_demo, 'soap'), ['000000000000000AAA'])
        self.assertEqual(extract(soql_demo, 'soap'), [])

        self.assertEqual(extract(json_demo, 'soql'), [])
        self.assertEqual(extract(soap_demo, 'soql'), [])
        self.assertEqual(extract(soql_demo, 'soql'), ['000000000000000AAA'])
