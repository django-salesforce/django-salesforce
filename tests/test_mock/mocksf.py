"""Mock requests for Salesforce (REST/SOAP API to database)

Principial differences to other packages:
- The same query should have different results before and after insert, update, delete
  (therefore not used "requests-mock" etc.)
- This module has several modes:
  "record": mode for re-writing small integration tests to create mock tests
  "playback": mode for running the tests fast from recorded data
  "mixed" mode is used like a silent "record" mode that is prepared to be
      switched to "record" mode inside the same session, e.g if a test test is
      extended by additional requests

    properties of modes:
        two sources or requests: application / recorded
        two sources or responses: Force.com server / recorded

        need to authentize before session?: (bool)
        record raw data or anonimize all ID
        record the traffic or to check and terminate at the first difference or
            to translate the historyrepla?
        cleanup after error or wait?
        a difference should be reported, but it an exception should not be raised before tearDown?
        * from application to server: * like a normal test
                                      * record all
                                      * check
                                      * check and record after difference
        * from playback to server: (check that the Force.com API is not changed)
        * nothing to server: response from playback: * only report differences
                                                     * stop a different request
                                                     * switch to server (replay and translate history)
        compare recorded requests
        compare test data

        Use raw recorded traffic or to try to find a nice formated equivalent record?
Parameters
    request_type: (None, 'application/json',... '*') The type '*' is for
        requests where the type and data should not be checked.
    data:  The recommended types are (str, None) A "dict" is possible, but
        it is not explicit enough for some data types.
    json:  it is unused and will be probably deprecated.
           It can be replaced by "json.dumps(request_json)"
"""
from typing import Optional, Set, Union
from unittest import mock  # pylint:disable=unused-import  # NOQA
import json as json_mod
import re

from django.db import connections
from django.test import SimpleTestCase

from django.conf import settings

import salesforce
# from salesforce.dbapi import settings
from salesforce.auth import MockAuth, TimeStatistics
from salesforce.dbapi import driver
from salesforce.dbapi.exceptions import DatabaseError
from salesforce.backend import DJANGO_22_PLUS
from salesforce.backend.test_helpers import sf_alias

APPLICATION_JSON = 'application/json;charset=UTF-8'


# the first part are not test cases, but helpers for a mocked network: MockTestCase, MockRequest


class MockRequestsSession(object):
    """Prepare mock session with expected requests + responses history

    expected:   iterable of MockJsonRequest
    testcase:  testcase object (for consistent assertion)
    """

    def __init__(self, testcase, expected=(), auth=None, old_session=None):
        self.index = 0
        self.testcase = testcase
        self.expected = list(expected)
        self.auth = auth or MockAuth('dummy alias', {'USER': ''}, _session='dummy login session')
        self.old_session = old_session

    def add_expected(self, expected_requests):
        if isinstance(expected_requests, (list, tuple)):
            self.expected.extend(expected_requests)
        else:
            self.expected.append(expected_requests)

    def request(self, method, url, data=None, **kwargs):
        """Assert the request equals the expected, return historical response"""
        # pylint:disable=too-many-locals
        mode = getattr(settings, 'SF_MOCK_MODE', 'playback')
        if mode == 'playback':
            expected = self.expected[self.index]
            msg = "Difference at request index %d (from %d)" % (self.index, len(self.expected))
            response = expected.request(method, url, data=data, testcase=self.testcase,
                                        msg=msg, **kwargs)
            self.index += 1
            return response
        if mode in ('record', 'mixed'):
            if not self.old_session:
                raise ValueError(
                    'If set SF_MOCK_MODE="record" then the global value or value '
                    'in setUp method must be "mixed" or "record".')
            new_url = url.replace('mock://', self.old_session.auth.instance_url)
            response = self.old_session.request(method, new_url, data=data, **kwargs)
            if mode == 'record':
                print()
                output = []
                output.append('"%s %s"' % (method, url))
                if data:
                    output.append("req=%r" % data)
                if 'json' in kwargs:
                    output.append("request_json=%r" % kwargs['json'])
                if response.text:
                    output.append("resp=%r" % response.text)

                request_type = kwargs.get('headers', {}).get('Content-Type', '')
                response_type = response.headers.get('Content-Type', '')
                basic_type = request_type or response_type
                if basic_type.startswith('application/json'):
                    request_class = MockJsonRequest
                else:
                    request_class = MockRequest
                    output.append("request_type=%r" % request_type)

                if response_type and (response_type != basic_type or request_class is MockRequest):
                    output.append("response_type=%r" % response_type)
                if response.status_code != 200:
                    output.append("status_code=%d" % response.status_code)
                if self.verbosity > 0:
                    print("=== MOCK RECORD {testcase}\n{class_name}(\n    {params})\n===".format(
                        class_name=request_class.__name__,
                        testcase=self.testcase,
                        params=',\n    '.join(output)
                        ))
            return response
        raise NotImplementedError("Not implemented SF_MOCK_MODE=%s" % mode)

    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)

    def post(self, url, data=None, json=None, **kwargs):  # pylint:disable=redefined-outer-name
        return self.request('POST', url, data=data, json=json, **kwargs)

    def patch(self, url, data=None, json=None, **kwargs):  # pylint:disable=redefined-outer-name
        return self.request('PATCH', url, data=data, json=json, **kwargs)

    def delete(self, url, **kwargs):
        return self.request('DELETE', url, **kwargs)

    def mount(self, prefix, adapter):
        pass

    def close(self) -> None:
        pass

    @property
    def verbosity(self) -> int:
        return getattr(settings, 'SF_MOCK_VERBOSITY', 1)


class MockRequest(object):
    """Recorded Mock request to be compared and response to be used

    for some unit tests offline
    If the parameter 'request_type' is '*' then the request is not tested
    """
    # pylint:disable=too-few-public-methods,too-many-instance-attributes
    default_type = None  # type: Optional[str]

    def __init__(self, method_url,  # pylint:disable=too-many-arguments
                 req=None, resp=None,
                 request_json=None,
                 request_type=None, response_type=None,
                 status_code=200, check_request=True):
        method, url = method_url.split(' ', 1)
        self.method = method
        self.url = url
        self.request_data = req
        self.response_data = resp
        self.request_json = request_json
        self.request_type = request_type or (self.default_type if method not in ('GET', 'DELETE') else '') or ''
        self.response_type = response_type
        self.status_code = status_code
        self.check_request = check_request

    def request(self, method, url, data=None, json=None, testcase=None, **kwargs):
        # pylint:disable=too-many-arguments,too-many-branches
        """Compare the request to the expected. Return the expected response."""
        if testcase is None:
            raise TypeError("Required keyword argument 'testcase' not found")
        msg = kwargs.pop('msg', None)
        if self.check_request:
            testcase.assertEqual(method.upper(), self.method.upper())
            testcase.assertEqual(url, self.url, msg=msg)
        if self.response_data:
            response_class = MockJsonResponse if self.default_type == APPLICATION_JSON else MockResponse
        else:
            response_class = MockResponse
        request_type = ''
        if json:
            assert not data
            data = json_mod.dumps(json)
            request_type = APPLICATION_JSON
        if (data or json) and 'headers' in kwargs:
            request_type = kwargs['headers'].pop('Content-Type', '') or request_type
        response = response_class(self.response_data,
                                  status_code=self.status_code,
                                  resp_content_type=self.response_type)
        if not self.check_request:
            return response

        if 'json' in self.request_type:
            testcase.assertJSONEqual(data, self.request_data, msg=msg)
        elif 'xml' in self.request_type:
            testcase.assertXMLEqual(data, self.request_data, msg=msg)
        elif self.request_type != '*':
            testcase.assertEqual(data, self.request_data, msg=msg)
        if self.request_type != '*':
            request_json = kwargs.pop('json', None)
            testcase.assertEqual(request_json, self.request_json, msg=msg)
        if self.request_type != '*':
            testcase.assertEqual(request_type.split(';')[0], self.request_type.split(';')[0], msg=msg)
        kwargs.pop('timeout', None)
        assert kwargs.pop('verify', True) is True  # TLS verify must not be False
        if 'json' in kwargs and kwargs['json'] is None:
            del kwargs['json']
        if 'headers' in kwargs and not kwargs['headers']:
            del kwargs['headers']
        if kwargs:
            raise NotImplementedError("unexpected args = %s (msg=%s) at url %s" % (kwargs, msg, url))
        return response


class MockJsonRequest(MockRequest):
    """Mock JSON request/response for some unit tests offline"""
    # pylint:disable=too-few-public-methods
    default_type = APPLICATION_JSON


class MockTestCase(SimpleTestCase):
    """
    Test case that uses recorded requests/responses instead of network
    """
    if DJANGO_22_PLUS:
        databases = {'salesforce'}  # type: Union[Set[str], str]
    else:
        allow_database_queries = True

    def setUp(self):
        # pylint:disable=protected-access
        mode = getattr(settings, 'SF_MOCK_MODE', 'playback')
        super(MockTestCase, self).setUp()
        connection = connections[sf_alias]
        if connection.vendor != 'salesforce':
            raise DatabaseError("MockTestCase can run only on Salesforce databases")
        if not connection.connection:
            connection.connect()
        if mode != 'playback':
            # if the mode is 'record' or 'mixed' we must create a real connection before mock
            if not connection.connection.sf_session:
                connection.make_session()
        connection = connection.connection
        self.sf_connection = connection
        self.save_session_auth = connection._sf_session, connection.sf_auth
        connection._sf_session = MockRequestsSession(testcase=self, old_session=connection._sf_session)
        connection.sf_auth = connection._sf_session.auth

        self.save_api_version = connection._api_version
        connection._api_version = getattr(self, 'api_version', salesforce.API_VERSION)
        # simulate a recent request (to not run a check for broken conection in the test)
        driver.time_statistics.expiration = 1E10

    def tearDown(self):
        if hasattr(self, '_outcome'):  # Python 3.4+
            result = self.defaultTestResult()  # these 2 methods have no side effects
            self._feedErrorsToResult(result, self._outcome.errors)
        else:  # Python 3.2 - 3.3 or 2.7
            result = getattr(self, '_outcomeForDoCleanups', self._resultForDoCleanups)  # pylint:disable=no-member
        error = self.list2reason(result.errors)
        failure = self.list2reason(result.failures)
        ok = not error and not failure
        # # demo:   report short info immediately (not important)
        # if not ok:
        #     typ, text = ('ERROR', error) if error else ('FAIL', failure)
        #     msg = [x for x in text.split('\n')[1:] if not x.startswith(' ')][0]
        #     print("\n%s: %s\n     %s" % (typ, self.id(), msg))

        connection = self.sf_connection
        session = connection._sf_session  # pylint:disable=protected-access
        if ok:
            self.assertEqual(session.index, len(session.expected), "Not all expected requests has been used")
        connection._sf_session, connection.sf_auth = self.save_session_auth  # pylint:disable=protected-access
        connection._api_version = self.save_api_version
        driver.time_statistics.expiration = TimeStatistics().expiration
        super(MockTestCase, self).tearDown()

    def list2reason(self, exc_list):
        if exc_list and exc_list[-1][0] is self:
            return exc_list[-1][1]

    def mock_add_expected(self, expected_requests):
        self.sf_connection._sf_session.add_expected(expected_requests)  # pylint:disable=protected-access


# class MockXmlRequest - only with different default content types


class MockResponse(object):
    """Mock response for some unit tests offline"""
    default_type = None  # type: Optional[str]

    def __init__(self, text, resp_content_type=None, status_code=200):
        self.text = text
        self.status_code = status_code
        self.content_type = resp_content_type if resp_content_type is not None else self.default_type

    def json(self, parse_float=None):
        return json_mod.loads(self.text.replace('...', ''), parse_float=parse_float)

    @property
    def headers(self):
        return {'Content-Type': self.content_type} if self.content_type else {}


class MockJsonResponse(MockResponse):
    default_type = APPLICATION_JSON


# Undocumented - useful for tests


def case_safe_sf_id(id_15):
    """
    Equivalent to Salesforce CASESAFEID()

    Convert a 15 char case-sensitive Id to 18 char case-insensitive Salesforce Id
    or check the long 18 char ID.

    Long  18 char Id are from SFDC API and from Apex. They are recommended by SF.
    Short 15 char Id are from SFDC formulas if omitted to use func CASESAFEID(),
    from reports or from parsed URLs in HTML.
    The long and short form are interchangable as the input to Salesforce API or
    to django-salesforce. They only need to be someway normalized if they are
    used as dictionary keys in a Python application code.
    """
    if not id_15:
        return None
    if len(id_15) not in (15, 18):
        raise TypeError("The string %r is not a valid Force.com ID")
    suffix = []
    for i in range(0, 15, 5):
        weight = 1
        digit = 0
        for char in id_15[i:i + 5]:
            if char not in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz':
                raise TypeError("The string %r is not a valid Force.com ID")
            if char.isupper():
                digit += weight
            weight *= 2
        suffix.append(chr(ord('A') + digit) if digit < 26 else str(digit - 26))
    out = ''.join(suffix)
    if len(id_15) == 18 and out != id_15[15:]:
        raise TypeError("The string %r is not a valid Force.com ID")
    return id_15[:15] + out


def check_sf_api_id(id_18):
    """
    Check the 18 characters long API ID, no exceptions
    """
    try:
        return case_safe_sf_id(id_18)
    except TypeError:
        return None


def extract_ids(data_text, data_type=None):
    """
    Extract all Force.com ID from REST/SOAP/SOQL request/response (for mock tests)

    Output: iterable of all ID and their positions
    Parameters: data_type:  can be in ('rest', 'soap', 'soql', None),
                    where None is for any unknown type
    """
    id_pattern = r'([0-9A-Za-z]{18})'
    pattern_map = {None: r'[">\']{}["<\']',
                   'rest': '"{}"',
                   'soap': '>{}<',
                   'soql': "'{}'"
                   }
    pattern = pattern_map[data_type].format(id_pattern)
    for match in re.finditer(pattern, data_text):
        txt = match.group(1)
        if case_safe_sf_id(txt):
            yield txt, (match.start(1), match.end(1))
