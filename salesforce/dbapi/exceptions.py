# All error types described in DB API 2 are implemented the same way as in
# Django (1.10 to 2.18)., otherwise some exceptions are not correctly reported in it.
import json
import sys
import warnings
PY3 = sys.version_info[0] == 3
text_type = str if PY3 else type(u'')
# pylint:disable=too-few-public-methods


class SalesforceWarning(Warning):
    def __init__(self, messages=None, response=None, verbs=None):
        self.data, self.response, self.verbs = (), None, None
        message = prepare_exception(self, messages, response, verbs)
        super(SalesforceWarning, self).__init__(message)


class Error(Exception if PY3 else StandardError):  # NOQA pylint:disable=undefined-variable
    #                                              # StandardError is undefined in PY3
    """
    Database error that can get detailed error information from a SF REST API response.

    customized for aproriate information, not too much or too little.
    """
    def __init__(self, messages=None, response=None, verbs=None):
        self.data, self.response, self.verbs = (), None, None
        message = prepare_exception(self, messages, response, verbs)
        super(Error, self).__init__(message)


class InterfaceError(Error):
    pass  # should be raised directly


class DatabaseError(Error):
    pass


class SalesforceError(DatabaseError):
    """Error reported by SFDC data instance in a REST API request.

    This class is for messages with ExceptionCode that can be searched in
    "SOAP API documentation"
    https://developer.salesforce.com/docs/atlas.en-us.api.meta/api/sforce_api_calls_concepts_core_data_objects.htm#exception_code_topic
    by the capitalized ExceptionCode: e.g. "DUPLICATE_VALUE \n some context about it"

    Subclasses are for messages created by django-salesforce.

    Timeout is also reported as a SalesforceError, because it can be frequently caused
    by SFDC by a slow query. There is no ambiguity.
    """


class DataError(SalesforceError):
    pass


class OperationalError(SalesforceError):
    pass  # e.g. network, auth


class IntegrityError(SalesforceError):
    pass  # e.g. foreign key (probably recently deleted obj)


class InternalError(SalesforceError):
    pass


class ProgrammingError(SalesforceError):
    pass  # e.g sql syntax


class NotSupportedError(SalesforceError):
    pass


class SalesforceAuthError(SalesforceError):
    """Error reported by SFDC in salesforce.auth at login request.

    The messages are typically very cryptic. (probably intentionally,
    to not disclosure more information to unathorized persons)

    Repeated errors of this class can lock the user account temporarily.
    """


def prepare_exception(obj, messages=None, response=None, verbs=None):
    """Prepare excetion params or only an exception message

    parameters:
        messages: list of strings, that will be separated by new line
        response: response from a request to SFDC REST API
        verbs: list of options about verbosity
    """
    # pylint:disable=too-many-branches
    verbs = set(verbs or [])
    known_options = ['method+url']
    if messages is None:
        messages = []
    if isinstance(messages, (text_type, str)):
        messages = [messages]
    assert isinstance(messages, list)
    assert not verbs.difference(known_options)

    data = None
    # a boolean from a failed response is False, though error messages in json should be decoded
    if response is not None and 'json' in response.headers.get('Content-Type', '') and response.text:
        data = json.loads(response.text)
        if data:
            data_0 = data[0]
            if 'errorCode' in data_0:
                subreq = ''
                if 'referenceId' in data_0:
                    subreq = " (in subrequest {!r})".format(data_0['referenceId'])
                messages = [data_0['errorCode'] + subreq] + messages
            if data_0.get('fields'):
                messages.append('FIELDS: {}'.format(data_0['fields']))
            if len(data) > 1:
                messages.append('MORE_ERRORS ({})'.format(len(data)))
    if 'method+url' in verbs:
        method = response.request.method
        url = response.request.url
        if len(url) > 100:
            url = url[:100] + '...'
        data_info = ''
        if (method in ('POST', 'PATCH') and
                (not response.request.body or 'json' not in response.request.headers['content-type'])):
            data_info = ' (without json request data)'
        messages.append('in {} "{}"{}'.format(method, url, data_info))
    separ = '\n    '
    if not PY3:
        messages = [x if isinstance(x, str) else x.encode('utf-8') for x in messages]
    messages = [x.replace('\n', separ) for x in messages]
    message = separ.join(messages)
    if obj:
        obj.data = data
        obj.response = response
        obj.verbs = verbs
    return message


def warn_sf(messages, response, verbs=None, klass=SalesforceWarning):
    """Issue a warning SalesforceWarning, with message combined from message and data from SFDC response"""
    warnings.warn(klass(messages, response, verbs), stacklevel=2)
