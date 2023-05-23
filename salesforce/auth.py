# django-salesforce
#
# by Hyneck Cernoch and Phil Christensen
# See LICENSE.md for details
#

"""
oauth login support for the Salesforce API

All data are ascii str.
"""

from abc import ABC, abstractmethod
from html import escape as html_escape
from subprocess import PIPE, Popen
from typing import Any, Callable, cast, Dict, List, Optional, Sequence, Type
from urllib.parse import parse_qs, urlencode, urlsplit
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import threading
import urllib

import requests
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase

from salesforce import API_VERSION
from salesforce.dbapi.common import get_thread_connections, get_max_retries, time_statistics
from salesforce.dbapi.exceptions import (
    SalesforceAuthError,  # error from SFCD
    OperationalError,     # authentication error by invalid usage
    import_string,
)
from salesforce.dbapi.exceptions import SalesforceError  # noqa unused # common superclass of above errors

log = logging.getLogger(__name__)

oauth_lock = threading.Lock()
# The static "oauth_data" is useful for efficient static authentication with
# multithread server, whereas the thread local data in connection.sf_auth
# are necessary if dynamic auth is used.
oauth_data = {}  # type: Dict[str, Dict[str, str]]


def base64urlencode(input_bytes: bytes) -> str:
    # see https://tools.ietf.org/html/rfc4648#section-5
    return base64.urlsafe_b64encode(input_bytes).decode('ascii').rstrip('=')


class SalesforceAuth(AuthBase, ABC):
    """
    Authentication object that encapsulates all auth settings and holds the auth token.

    Its data is sufficient to can create a `connection` to SF data server.

    It is recommended (easier) to create subclasses from GlobalStaticAuth or from
    DynamicAuth, not directly from SalesforceAuth.

    SalesforceAuth(db_alias, settings_dict)
            A concrete subclass of SalesforceAuth should be specified in
            `settings_dict['AUTH']` as a string.
            The default is "salesforce.auth.SalesforcePasswordAuth",
      or

    SalesforceAuth(db_alias, settings_dict=None, _session)  used only in tests

    Methods that can be customized:
        get_token():        Get a token and url (that are saved here) or ask for a new
        reauthenticate():   Force to ask for a new token for the same user, not a saved token.
                            It is used after expired token error.
        validate_settings(): Validate the settings_dict before it is used

    callback from requests:
        __call__(r):        used for `requests` package
                            http://docs.python-requests.org/en/latest/user/advanced/#custom-authentication
    """

    # The key 'ENGINE' in settings_dict is required only by Django
    # to can find django-salesforce. It doesn't make sense to check 'ENGINE' here.
    required_fields = []  # type: Sequence[str]

    def __init__(self, db_alias: str, settings_dict: Optional[Dict[str, Any]] = None,
                 _session: Optional[requests.Session] = None) -> None:
        """
        Set values for authentication
            Params:
                db_alias:  The database alias e.g. the default SF alias 'salesforce'.
                        The 'alias' must be unique (It is not possible to open more
                        connections with the same alias from the same thread.)
                settings_dict: It is only important for the first connecting.
                        It should be e.g. django.conf.settings.DATABASES['salesforce'],
                        because it is not known initially in the connection.settings_dict.
                _session: Only for tests
        """
        if settings_dict:
            self.settings_dict = settings_dict
        else:
            assert db_alias
            self.settings_dict = get_thread_connections()[db_alias].settings_dict

        self.db_alias = db_alias
        self.validate_settings()
        # None: static, {}: dynamic unauthorized, non-empty dict: authorized dynamic
        self.dynamic = None   # type: Optional[Dict[str, str]]
        self._session = _session or requests.Session()

    @abstractmethod
    def authenticate(self) -> Dict[str, str]:
        pass

    def authenticate_and_cache(self) -> Dict[str, str]:
        """authenticate and save the result to cache (in static auth)"""
        return self.authenticate()

    @abstractmethod
    def get_auth(self) -> Dict[str, str]:
        """
        Cached value of authenticate()
        """

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        """Standard auth hook on the "requests" request r"""
        access_token = self.get_auth()['access_token']
        r.headers['Authorization'] = 'OAuth %s' % access_token
        return r

    @abstractmethod
    def reauthenticate(self) -> str:
        return ''

    @property
    def instance_url(self) -> str:
        data = self.get_auth()
        return data['instance_url'] if data else ''

    def validate_settings(self) -> None:
        missing_keys = set(self.required_fields).difference(k for k, v in self.settings_dict.items() if v)
        if missing_keys:
            raise OperationalError("Required keys %r are missing from '%s' database settings or are empty." %
                                   (missing_keys, self.db_alias))
        if self.settings_dict.get('HOST'):
            try:
                urlsplit(self.settings_dict['HOST'])
            except Exception as e:
                raise OperationalError("'HOST' key in '%s' database settings should be a URL: %s" %
                                       (self.db_alias, e))

    @staticmethod
    def create_subclass_instance(db_alias: str, settings_dict: Dict[str, Any],
                                 _session: Optional[requests.Session] = None) -> 'SalesforceAuth':
        """Create an instance of a subclass according to settings_dict"""
        auth_class_string = settings_dict.get('AUTH', 'salesforce.auth.SalesforcePasswordAuth')
        subclass = import_string(auth_class_string)  # type: Type[SalesforceAuth]
        assert issubclass(subclass, SalesforceAuth)
        return subclass(db_alias, settings_dict, _session=_session)


# === first subclass level

class StaticGlobalAuth(SalesforceAuth):

    @abstractmethod
    def authenticate(self) -> Dict[str, str]:
        """
        Authenticate to the Salesforce API with the provided credentials.

        This function will be called only if a token is not in this object or in the auth cache.
        """

    def authenticate_and_cache(self) -> Dict[str, str]:
        return self.get_auth()

    def get_auth(self) -> Dict[str, str]:
        """
        Cached value of authenticate()
        """
        # If another thread is running inside this method, wait for it to
        # finish. Always release the lock no matter what happens in the block
        db_alias = self.db_alias
        with oauth_lock:
            if db_alias not in oauth_data:
                oauth_data[db_alias] = self.authenticate()
            return oauth_data[db_alias]

    def del_token(self) -> None:
        """Forget the token"""
        with oauth_lock:
            if self.db_alias in oauth_data:
                del oauth_data[self.db_alias]

    def reauthenticate(self) -> str:
        assert not self.dynamic
        self.del_token()
        return self.get_auth()['access_token']

    def checked_auth_response(self, response: requests.Response) -> Dict[str, str]:
        """Verify the authentication response, incluging the signature"""
        if response.status_code == 200:
            response_data = response.json()  # type: Dict[str, str]
            calc_signature = (
                base64.b64encode(
                    hmac.new(
                        key=self.settings_dict['CONSUMER_SECRET'].encode('ascii'),
                        msg=(response_data['id'] + response_data['issued_at']).encode('ascii'),
                        digestmod=hashlib.sha256
                    ).digest()
                )
            ).decode('ascii')
            if calc_signature != response_data['signature']:
                raise OperationalError('Invalid auth signature received')
        else:
            raise SalesforceAuthError("oauth failed: %s: %s" % (self.settings_dict['USER'], response.text))
        return response_data


class DynamicAuth(SalesforceAuth):
    """
    These public methods shoud be called from your code (usually from a middleware)

        dynamic_start(access_token, instance_url):  Set authentication data
        dynamic_end():                              Delete authentication data

        This can be set by Django request in the middleware code by:
            connections['salesforce'].sf_auth.dynamic_start(access_token, instance_url)
    """

    required_fields = []  # type: List[str]

    def dynamic_start(self, access_token: str, instance_url: str, **kw: Any) -> None:
        """
        Set the access_token and instance_url dynamically to another user.

        The token must be valid for some time because the basic method has
        no possibility to refresh it.

        More parameters can be set in subclasses e.g. a refresh token.
        """
        self.dynamic = {'access_token': str(access_token), 'instance_url': str(instance_url)}
        self.dynamic.update(kw)

    def dynamic_end(self) -> None:
        """Clear the dynamic authenticate data."""
        self.dynamic = {}

    def authenticate(self) -> Dict[str, str]:
        return {}  # the client can and must start without a connection

    def reauthenticate(self) -> str:
        self.dynamic = {'invalid': 'invalid'}  # invalidate the dynamic data
        raise SalesforceAuthError("Can never reauthenticate a token while in a Dynamically authenticated code.")

    def get_auth(self) -> Dict[str, str]:
        if self.dynamic:
            return self.dynamic
        raise OperationalError("DynamicAuth can be used only between dynamic_start() and dynamic_end()")


# === second, third, fourth... subclass levels

# --- Pasword

class SalesforcePasswordAuth(StaticGlobalAuth):
    """
    Attaches "OAuth 2.0 Salesforce Password authentication" to the `requests` Session

    Static auth data are cached thread safely between threads. Thread safety
    is provided by the ancestor class.
    """

    required_fields = ['HOST', 'CONSUMER_KEY', 'CONSUMER_SECRET', 'USER', 'PASSWORD']

    def authenticate(self) -> Dict[str, str]:
        """
        Authenticate to the Salesforce API with the provided credentials (password).
        """
        settings_dict = self.settings_dict
        url = ''.join([settings_dict['HOST'], '/services/oauth2/token'])

        log.info("authentication to %s as %s", settings_dict['HOST'], settings_dict['USER'])
        if settings_dict['HOST'] not in self._session.adapters:
            # a repeated mount to the same prefix would cause a warning about unclosed SSL socket
            self._session.mount(settings_dict['HOST'], HTTPAdapter(max_retries=get_max_retries()))
        auth_params = {
            'grant_type':    'password',
            'client_id':     settings_dict['CONSUMER_KEY'],
            'client_secret': settings_dict['CONSUMER_SECRET'],
            'username':      settings_dict['USER'],
            'password':      settings_dict['PASSWORD'],
        }
        time_statistics.update_callback(url, self.ping_connection)
        response = self._session.post(url, data=auth_params)
        return self.checked_auth_response(response)

    def ping_connection(self) -> None:
        try:
            self._session.get(self.settings_dict['HOST'], timeout=1.0)
        except requests.exceptions.RequestException:
            pass


class PasswordAndDynamicAuth(SalesforcePasswordAuth, DynamicAuth):
    # not tested yet enough
    """
    Start as password authentication. Switch to dynamic after ".dynamic_start(...)".
    It never uses the static auth more after the end of dynamic.
    """

    required_fields = ['HOST']

    def get_auth(self) -> Dict[str, str]:
        if self.dynamic is None:
            return super().get_auth()
        return DynamicAuth.get_auth(self)

    def del_token(self) -> None:
        """Delete the static token and wait for dynamic"""
        super().del_token()
        self.dynamic = None

    def reauthenticate(self) -> str:
        if self.dynamic is None:  # pylint:disable=no-else-return
            return super().reauthenticate()
        else:
            return DynamicAuth.reauthenticate(self)  # raises


class SimpleSfPasswordAuth(StaticGlobalAuth):
    """
    The simplest authentication from simple-salesforce
    """

    required_fields = ['HOST', 'USER', 'PASSWORD']

    def authenticate(self) -> Dict[str, str]:
        """
        Authenticate to the Salesforce API with the provided credentials (password).
        """
        def tag_content(tag: str) -> str:
            match = re.search('<{tag}>(.*)</{tag}>'.format(tag=tag), response.text)
            assert match
            return match.group(1)

        simple_soap_login_template = (
            """<?xml version="1.0" encoding="utf-8" ?>
            <env:Envelope
                    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                    xmlns:env="http://schemas.xmlsoap.org/soap/envelope/"
                    xmlns:urn="urn:partner.soap.sforce.com">
                <env:Header>
                    <urn:CallOptions>
                        <urn:client>{client_id}</urn:client>
                        <urn:defaultNamespace>sf</urn:defaultNamespace>
                    </urn:CallOptions>
                </env:Header>
                <env:Body>
                    <n1:login xmlns:n1="urn:partner.soap.sforce.com">
                        <n1:username>{username}</n1:username>
                        <n1:password>{password}</n1:password>
                    </n1:login>
                </env:Body>
            </env:Envelope>
            """
        )
        settings_dict = self.settings_dict
        request_body = simple_soap_login_template.format(
            username=html_escape(settings_dict['USER']),
            password=html_escape(settings_dict['PASSWORD']),  # including a personal security_token
            client_id='django-salesforce',
        )
        request_headers = {'content-type': 'text/xml', 'charset': 'UTF-8', 'SOAPAction': 'login'}
        url = '{}/services/Soap/u/{}'.format(settings_dict['HOST'], API_VERSION)
        log.info("authentication to %s as %s", settings_dict['HOST'], settings_dict['USER'])
        if settings_dict['HOST'] not in self._session.adapters:
            self._session.mount(settings_dict['HOST'], HTTPAdapter(max_retries=get_max_retries()))
        response = self._session.post(url, request_body, headers=request_headers)
        if response.status_code != 200:
            raise SalesforceAuthError("login failed for user '%s': %s" % (
                self.settings_dict['USER'], tag_content('faultstring'))
            )
        match_instance_url = re.match(r'(https://[^/]+)/', tag_content('serverUrl'))
        assert match_instance_url
        instance_url = match_instance_url.group(1)
        return {'access_token': tag_content('sessionId'), 'instance_url': instance_url}


# --- SFDX

class SfdxWebAuth(StaticGlobalAuth):
    """
    Authenticate by "auth:web:login" in SFDX command line application

    no private data are saved to disk by django-salesforce, only data by sfdx
    """
    required_fields = ['HOST', 'USER']
    data = None  # type:Dict[str, Any]

    def authenticate(self) -> Dict[str, str]:
        host = self.settings_dict['HOST']
        user = self.settings_dict['USER']
        # consumer_key = self.settings_dict.get('CONSUMER_KEY')
        log.info("authentication by SFDX to %s as %s", host, user)
        data = self.ask_sfdx_org_data(user)
        if 'stack' in data:  # that means an error that is not raised

            cmd = 'sfdx force:auth:web:login --json --instanceurl'.split() + [host]

            data = self.sfdx(cmd)
            if data['username'] != user:
                raise SalesforceAuthError("Login by %r is requied, but you have logged in as a different "
                                          "user %r" % (user, data['username']))
        return {'access_token': data['accessToken'], 'instance_url': data['instanceUrl']}

    @abstractmethod
    def ask_sfdx_org_data(self, user: str) -> Dict[str, Any]:
        # stub - because not implemented in this parent
        # return {'stack': None, 'message': 'search is not used in this class'}
        pass

    def sfdx(self, command: Sequence[str], no_raise: str = '') -> Dict[str, Any]:
        """Run a SFDX command. Don't raise on the expected error names (comma delimited)"""
        # not intercept OSError e.g. file not found - raise directly
        # stderr is not redirected, because it can be used for some interactive dialogs
        with Popen(command, stdout=PIPE) as proc:
            stdout, _ = proc.communicate()
            returncode = proc.returncode

        if returncode != 0:
            self.data = {}
            # proc.returncode is the same as json "status" (and json "exitCode" if not zero)
            try:
                data = json.loads(stdout)
                assert isinstance(data, dict)
                msg = "SFDX error {}: {}".format(data['name'], data['message'])
                if data['name'] in no_raise.split(','):
                    return data
            except (json.decoder.JSONDecodeError, KeyError):
                msg = "SFDX invalid JSON output"
            print("COMMAND: {}".format(' '.join(command)))
            raise SalesforceAuthError(msg)
        data = json.loads(stdout)
        assert data['status'] == 0
        self.data = data['result']
        return self.data


class SfdxOrgWebAuth(SfdxWebAuth):
    """
    Authenticate by "org:display" or "auth:web:login" in SFDX CLI
    """

    required_fields = ['HOST', 'USER']

    def ask_sfdx_org_data(self, user: str) -> Dict[str, Any]:
        """Ask SFDX if it the user is connected to it"""

        cmd = 'sfdx force:org:display --json -u'.split() + [user]

        # 'NoOrgFound' is a possible deprecated error name in favour of 'NamedOrgNotFound'
        # other errors are raised, e.g. network errors
        data = self.sfdx(cmd, no_raise='NamedOrgNotFound,NoOrgFound,oauthInvalidGrant')
        if 'stack' not in data:
            assert data['username'] == user and 'name' not in data
        return data


class SfdxOrgAuth(SfdxOrgWebAuth):
    """
    Authenticate by "org:display" in SFDX CLI
    """

    required_fields = ['USER']

    def authenticate(self) -> Dict[str, str]:
        host = self.settings_dict.get('HOST')
        user = self.settings_dict['USER']
        log.info("authentication by SFDX as %s", user)
        data = self.ask_sfdx_org_data(user)
        if 'stack' in data:
            if host == 'https://login.salesforce.com':
                instance_msg = ''
            else:
                instance_msg = '--instanceurl ' + (host or '<login_instance_url>')
            raise SalesforceAuthError(
                "User %r is not connected to SFDX. You can login manually:\n"
                "    sfdx force:auth:web:login %s" % (user, instance_msg)
            )
        return {'access_token': data['accessToken'], 'instance_url': data['instanceUrl']}


# ---

class RefreshTokenAuth(StaticGlobalAuth):
    """
    Authenticate by refresh token or get the refresh token interactive

    check "Refresh Token Policy" should be "Refresh token is valid until revoked"
    """
    # get refresh_token
    # https://help.salesforce.com/articleView?id=remoteaccess_oauth_web_server_flow.htm&type=5
    # use refresh token
    # https://help.salesforce.com/articleView?id=remoteaccess_oauth_refresh_token_flow.htm&type=5

    redirect_uri = None  # type: str
    code_verifier = None  # type: str

    required_fields = ['HOST', 'USER', 'CONSUMER_KEY', 'CONSUMER_SECRET', 'REFRESH_TOKEN']

    def authenticate(self, old_auth: Optional[Dict[str, str]] = None  # pylint:disable=arguments-differ
                     ) -> Dict[str, str]:
        host = self.settings_dict['HOST']
        user = self.settings_dict['USER']
        refresh_token = self.settings_dict['REFRESH_TOKEN']
        if refresh_token == '?':
            if not old_auth:
                return self.get_refresh_token_interactive()
            refresh_token = old_auth['refresh_token']
            if refresh_token == 'invalid':
                raise SalesforceAuthError("Invalid refresh token in database %r" % self.db_alias)

        log.info("authentication by Refresh Token to %s as %s", host, user)

        url = self.settings_dict['HOST'] + '/services/oauth2/token'
        data = urlencode(dict(
            grant_type='refresh_token',
            client_id=self.settings_dict['CONSUMER_KEY'],
            client_secret=self.settings_dict['CONSUMER_SECRET'],
            refresh_token=refresh_token,
        ))
        headers = {'Content-type': 'application/x-www-form-urlencoded'}
        response = requests.post(url, data=data, headers=headers)
        try:
            auth_data = self.checked_auth_response(response)
        except SalesforceAuthError:
            if old_auth and 'invalid_grant' in response.text:
                old_auth['refresh_token'] = 'invalid'
            raise SalesforceAuthError("Invalid refresh token in database %r" % self.db_alias)
        auth_data.setdefault('refresh_token', refresh_token)
        return auth_data

    def get_auth(self) -> Dict[str, str]:
        """
        Cached value of authenticate()
        """
        # If another thread is running inside this method, wait for it to
        # finish. Always release the lock no matter what happens in the block
        db_alias = self.db_alias
        with oauth_lock:
            if 'access_token' not in oauth_data.get(db_alias, {}):
                oauth_data[db_alias] = self.authenticate(oauth_data.get(self.db_alias))
            return oauth_data[db_alias]

    def del_token(self) -> None:
        """Forget the token"""
        with oauth_lock:
            if 'access_token' in oauth_data.get(self.db_alias, {}):
                del oauth_data[self.db_alias]['access_token']

    def reauthenticate(self) -> str:
        assert not self.dynamic
        with oauth_lock:
            if 'access_token' in oauth_data.get(self.db_alias, {}):
                del oauth_data[self.db_alias]['access_token']
        return self.get_auth()['access_token']

    def get_refresh_token_interactive(self) -> Dict[str, Any]:
        """Get a refresh token by dialog with the developer on the concole.

        The dialog is: visit a URL manually, authorize and paste the final URL to console
        """
        url_login = self.get_auth_redirect_url()
        print()
        print(url_login)
        print("\nOpen the URL above in your browser and follow (optionally Login to Salesforce, "
              "approve the application to access) Copy the URL where you are finally redirected. "
              "Paste it here and Press Enter (The URL expires in 15 minutes.)\n"
              )
        final_url = input('? ')
        auth_data = self.authorization_code_processing(final_url)
        print("\nCopy this line to settings DATABASES[%r]:\n        "
              "'REFRESH_TOKEN': %r," % (self.db_alias, auth_data['refresh_token']))
        return auth_data

    def get_auth_redirect_url(self, user: Optional[str] = None) -> str:
        host = self.settings_dict['HOST']
        user_hint = user or self.settings_dict['USER']
        if 'CALLBACK_URL' in self.settings_dict:
            self.redirect_uri = self.settings_dict['CALLBACK_URL']
        else:
            self.redirect_uri = host
        log.info("Get a Refresh Token for user %s", user_hint)

        # see https://developer.salesforce.com/forums/?id=906F0000000D6kjIAC
        self.code_verifier = base64urlencode(os.urandom(128))
        self.code_verifier = base64urlencode(os.urandom(32))
        # code_verifier = base64urlencode(32 * 'A'.encode('ascii'))
        code_challenge = base64urlencode(hashlib.sha256(self.code_verifier.encode('ascii')).digest())
        url_params = {
            'client_id': self.settings_dict['CONSUMER_KEY'],
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            # optional
            'scope': self.settings_dict.get('OAUTH_SCOPE', 'api refresh_token'),  # or 'full refresh_token'
            'prompt': 'consent',
            'code_challenge': code_challenge,
            }
        if user_hint:
            url_params['login_hint'] = user_hint
        query = urlencode(url_params,  quote_via=quote_no_plus)
        url_login = cast(str, self.settings_dict['HOST']) + '/services/oauth2/authorize?' + query
        return url_login

    def authorization_code_processing(self, final_url: str) -> Dict[str, Any]:
        query = parse_qs(urlsplit(final_url).query)
        if 'error' in query:
            raise SalesforceError("Salesforce OAuth2 Error: {query}".format(query=query))
        code, = query['code']
        url = self.settings_dict['HOST'] + '/services/oauth2/token'
        data = urlencode(dict(
            grant_type='authorization_code',
            code=code,
            client_id=self.settings_dict['CONSUMER_KEY'],
            client_secret=self.settings_dict['CONSUMER_SECRET'],
            redirect_uri=self.redirect_uri,
            code_verifier=self.code_verifier,
            format='json',
        ))
        headers = {'Content-type': 'application/x-www-form-urlencoded'}
        response = requests.post(url, data=data, headers=headers)
        auth_data = self.checked_auth_response(response)
        return auth_data


# -- special internal auth (for tests)

class MockAuth(SalesforceAuth):
    """Dummy authentication for offline Mock tests"""

    def authenticate(self) -> Dict[str, str]:
        return {'instance_url': 'mock://'}

    def get_auth(self) -> Dict[str, str]:
        # this is never cached
        return self.authenticate()

    def reauthenticate(self) -> str:
        return ''

    def del_token(self) -> None:
        pass


quote_no_plus = urllib.parse.quote  # type: Callable[[str, str, str, str], str]
