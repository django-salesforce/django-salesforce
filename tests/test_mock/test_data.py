from django.db import connections

from salesforce.dbapi.exceptions import SalesforceError
from tests.test_mock.mocksf import MockJsonRequest, MockRequest, MockTestCase
from tests.test_mock.mocksf import mock  # NOQA pylint:disable=unused-import

# :%s@mock://@mock://@


class MockTest(MockTestCase):
    api_version = '20.0'

    def setUp(self):
        super(MockTest, self).setUp()
        self.cursor = connections['salesforce'].cursor()

    # ---------------------

    def test_version(self):
        "Get the Salesforce Version"
        self.mock_add_expected(
            MockJsonRequest(
                "GET mock:///services/data/",
                resp="""[
                    {
                        "version":"20.0",
                        "url":"/services/data/v20.0",
                        "label":"Winter '11"
                    }
                    ...
                ]""",))
        ret = self.cursor.versions_request()
        self.assertEqual(ret, [{'version': '20.0', 'url': '/services/data/v20.0', 'label': "Winter '11"}])

    # ---------------------

    def test_resources(self):
        "Get a List of Resources"
        self.mock_add_expected(
            MockJsonRequest(
                "GET mock:///services/data/v20.0/",
                resp="""{
                    "sobjects" : "/services/data/v20.0/sobjects",
                    "search" : "/services/data/v20.0/search",
                    "query" : "/services/data/v20.0/query",
                    "recent" : "/services/data/v20.0/recent"
                    ...
                }""",))
        ret = self.cursor.urls_request()
        self.assertEqual(ret['sobjects'], '/services/data/v20.0/sobjects')

    # ---------------------

    def test_foo(self):
        "..."
        self.mock_add_expected(
            MockJsonRequest(
                "GET mock:///services/data/v20.0/",
                resp="""
                {
                    ...
                }""",))
        ret = self.cursor.urls_request()
        self.assertEqual(ret, {})

# ---------------------


class SObjectCollectionsTest(MockTestCase):
    """
    Examples from SObject Collections
    https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_composite_sobjects_collections.htm
    """
    api_version = '42.0'

    def setUp(self):
        super(SObjectCollectionsTest, self).setUp()
        self.cursor = connections['salesforce'].cursor()  # TODO not important

    def test_create(self):
        "Create Multiple Records with Fewer Round-Trips"
        # This test data were recorded from REST API documentation in August 2016

        # Simulate a request and response call without all_or_none
        request_allornone_false = """
        {
           "allOrNone" : false,
           "records" : [{
              "attributes" : {"type" : "Account"},
              "Name" : "example.com",
              "BillingCity" : "San Francisco"
           }, {
              "attributes" : {"type" : "Contact"},
              "LastName" : "Johnson",
              "FirstName" : "Erica"
           }]
        }"""
        resp_1 = MockJsonRequest(
            "POST mock:///services/data/v42.0/composite/sobjects",
            request_allornone_false,
            resp="""
            [
               {
                  "id" : "001RM000003oLnnYAE",
                  "success" : true,
                  "errors" : [ ]
               },
               {
                  "id" : "003RM0000068xV6YAI",
                  "success" : true,
                  "errors" : [ ]
               }
            ]"""
        )
        self.mock_add_expected(resp_1)
        data = [
            dict(type_="Account", Name="example.com", BillingCity="San Francisco"),
            dict(type_="Contact", LastName="Johnson", FirstName="Erica")
        ]

        ret = self.cursor.db.connection.sobject_collections_request('POST', data, all_or_none=False)
        # the primary keys start with '001' (Account) and '003' (Contact'
        self.assertEqual([x[:3] for x in ret], ['001', '003'])

        # Simulate the same repeated request after the previous.
        # Expect that duplicates are not allowed by SFDC instance configuration
        resp_2 = MockJsonRequest(
            "POST mock:///services/data/v42.0/composite/sobjects",
            request_allornone_false,
            resp="""
            [
               {
                  "success" : false,
                  "errors" : [
                     {
                        "statusCode" : "DUPLICATES_DETECTED",
                        "message" : "Use one of these records?",
                        "fields" : [ ]
                     }
                  ]
               },
               {
                  "id" : "003RM0000068xVCYAY",
                  "success" : true,
                  "errors" : [ ]
               }
            ]""",
        )
        self.mock_add_expected(resp_2)
        with self.assertRaises(SalesforceError) as cm:
            ret = self.cursor.db.connection.sobject_collections_request('POST', data, all_or_none=False)
        self.assertIn('Account  DUPLICATES_DETECTED', cm.exception.args[0])

        # simulate the same, but with all_or_none. (One error reported and one operation rollback)
        request_allornone_true = request_allornone_false.replace('"allOrNone" : false', '"allOrNone" : true')
        resp_3 = MockJsonRequest(
            "POST mock:///services/data/v42.0/composite/sobjects",
            request_allornone_true,
            resp="""
            [
               {
                  "success" : false,
                  "errors" : [
                     {
                        "statusCode" : "DUPLICATES_DETECTED",
                        "message" : "Use one of these records?",
                        "fields" : [ ]
                     }
                  ]
               },
               {
                  "success" : false,
                  "errors" : [
                     {
                        "statusCode" : "ALL_OR_NONE_OPERATION_ROLLED_BACK",
                        "message" : "Record rolled back because not all records were valid and the request was """
                 """using AllOrNone header",
                        "fields" : [ ]
                     }
                  ]
               }
            ]""",
        )
        self.mock_add_expected(resp_3)
        with self.assertRaises(SalesforceError) as cm:
            ret = self.cursor.db.connection.sobject_collections_request('POST', data, all_or_none=True)
        self.assertIn('Account  DUPLICATES_DETECTED', cm.exception.args[0])

        # with mock.patch.object(self.cursor.db.connection, 'composite_type', 'composite'):
        #    ret = self.cursor.db.connection.sobject_collections_request('POST', data, all_or_none=True)


def parse_this():
    # OAuth error codes are in
    # https://support.salesforce.com/articleView?id=remoteaccess_errorcodes.htm&type=5

    # this is the error if the method was POST/PATCH and forgot Content-Type ".../json"
    #   response.text.startswith('<response><faultcode>LOGIN_OAUTH_INVALID_TOKEN')
    return MockRequest(
        '...', request_type='application/xml',
        status_code='401',
        # response headers {'Sfdc-OAuth-Error': '1703',...}
        response_type='text/html; charset=UTF-8',
        req="""
            <response>
            <faultcode>LOGIN_OAUTH_INVALID_TOKEN(db=1703,api=LOGIN_OAUTH_INVALID_TOKEN)</faultcode>
            <error>Failed: Invalid Token</error>
            </response>"""
    )
