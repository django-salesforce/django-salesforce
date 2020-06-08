# All error types described in DB API 2 are implemented the same way as in
# Django (1.11 to 3.0)., otherwise some exceptions are not correctly reported in it.
from importlib import import_module
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Type, Union
import json
import requests  # noqa
import warnings
# pylint:disable=too-few-public-methods


# === Forward defs  (they are first due to dependency)

class FakeReq:
    """A Fake Request is used for compatible error reporting in "composite" subrequests."""
    # pylint:disable=too-few-public-methods,too-many-arguments
    def __init__(self,
                 method: str,
                 url: str,
                 data: str,        # ?? Union[str, List[Any], Dict[str, Any]],
                 headers: Optional[Dict[str, str]] = None,
                 context: Optional[Dict[Any, Any]] = None
                 ) -> None:
        self.method = method
        self.url = url
        self.data = data
        self.headers = headers or {}  # type: Dict[str, str]
        self.context = context or {}  # type: Dict[Any, Any]  # the key is Union[str, int]

    @property
    def body(self) -> str:
        if isinstance(self.data, str):
            return self.data
        return json.dumps(self.data)


class FakeResp:  # pylint:disable=too-few-public-methods,too-many-instance-attributes
    """A Fake Response is used for compatible error reporting in "composite" subrequests."""
    def __init__(self, status_code: int, headers: Mapping[str, str], text: str, request: FakeReq) -> None:
        self.status_code = status_code
        self.text = text
        self.request = request
        self.headers = headers

        self.reason = None


GenResponse = requests.Response  # (requests.Response, 'FakeResp')


# === Exception defs

class SalesforceWarning(Warning):
    def __init__(self,
                 messages: Optional[Union[str, List[str]]] = None,
                 response: Optional[GenResponse] = None,
                 verbs: Optional[Iterable[str]] = None
                 ) -> None:
        self.data = []  # type: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]]
        self.response = None  # type: Optional[GenResponse]
        self.verbs = None  # type: Optional[Set[str]]
        message = prepare_exception(self, messages, response, verbs)
        super(SalesforceWarning, self).__init__(message)


class Error(Exception):
    """
    Database error that can get detailed error information from a SF REST API response.

    customized for aproriate information, not too much or too little.
    """
    def __init__(self,
                 messages: Optional[Union[str, List[str]]] = None,
                 response: Optional[GenResponse] = None,
                 verbs: Optional[Iterable[str]] = None
                 ) -> None:
        self.data = []  # type: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]]
        self.response = None  # type: Optional[GenResponse]
        self.verbs = None  # type: Optional[Set[str]]
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


def prepare_exception(obj: Union[Error, SalesforceWarning],
                      messages: Optional[Union[str, List[str]]] = None,
                      response: Optional[GenResponse] = None,
                      verbs: Optional[Iterable[str]] = None
                      ) -> str:
    """Prepare excetion params or only an exception message

    parameters:
        messages: list of strings, that will be separated by new line
        response: response from a request to SFDC REST API
        verbs: list of options about verbosity
    """
    # pylint:disable=too-many-branches
    verbs_ = set(verbs or [])
    known_options = ['method+url']
    if messages is None:
        messages = []
    if isinstance(messages, str):
        messages = [messages]
    assert isinstance(messages, list)
    assert not verbs_.difference(known_options)

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
    if 'method+url' in verbs_:
        assert response is not None and response.request.url
        method = response.request.method
        url = response.request.url
        if len(url) > 100:
            url = url[:100] + '...'
        data_info = ''
        if (method in ('POST', 'PATCH') and
                (not response.request.body or 'json' not in response.request.headers.get('content-type', ''))):
            data_info = ' (without json request data)'
        messages.append('in {} "{}"{}'.format(method, url, data_info))
    separ = '\n    '
    messages = [x.replace('\n', separ) for x in messages]
    message = separ.join(messages)
    if obj:
        obj.data = data
        obj.response = response
        obj.verbs = verbs_
    return message


def warn_sf(messages: Union[str, List[str]],
            response: Optional[GenResponse],
            verbs: Optional[Iterable[str]] = None,
            klass: Type[SalesforceWarning] = SalesforceWarning
            ) -> None:
    """Issue a warning SalesforceWarning, with message combined from message and data from SFDC response"""
    warnings.warn(klass(messages, response, verbs), stacklevel=2)


def import_string(dotted_path: str) -> Any:
    # copied from django.utils.module_loading
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError as err:
        raise ImportError("%s doesn't look like a module path" % dotted_path) from err

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError as err:
        raise ImportError('Module "%s" does not define a "%s" attribute/class' % (
            module_path, class_name)
        ) from err
