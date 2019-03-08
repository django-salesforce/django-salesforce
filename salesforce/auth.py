# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
oauth login support for the Salesforce API

All data are in ascii. Therefore the type str is good for both Python 2.7
and 3.4+. (The type str ascii is automatically adjusted to unicode in
Python 2, if necessary, but the unicode ascii could force an automatic
faulting conversion of other non-ascii str to unicode.)
Accepted parameters are both str or unicode in Python 2.
"""

import base64
import hashlib
import hmac
import logging
import threading

import requests
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase

from salesforce.dbapi import connections, get_max_retries
from salesforce.dbapi.exceptions import DatabaseError, IntegrityError, SalesforceAuthError

# TODO hy: more advanced methods with ouathlib can be implemented, but
#      the simple doesn't require a special package.

log = logging.getLogger(__name__)

oauth_lock = threading.Lock()
# The static "oauth_data" is useful for efficient static authentication with
# multithread server, whereas the thread local data in connection.sf_session.auth
# are necessary if dynamic auth is used.
oauth_data = {}


class SalesforceAuth(AuthBase):
    """
    Authentication object that encapsulates all auth settings and holds the auth token.

    It is sufficient to create a `connection` to SF data server instead of
    specific parameters for specific auth methods.

    required public methods:
        __ini__(db_alias, .. optional params, _session)  It sets the parameters
                            that needed to authenticate later by the respective
                            type of authentication.
                            A non-default `_session` for `requests` can be provided,
                            especially for tests.
        authenticate():     Ask for a new token (customizable method)

        del_token():        Forget token (both static and dynamic eventually)
    optional public (for your middleware)
        dynamic_start(access_token, instance_url):
                            Replace the static values by the dynamic
                            (change the user and url dynamically)
        dynamic_end():      Restore the previous static values
    private:
        get_token():        Get a token and url saved here or ask for a new
        reauthenticate():   Force to ask for a new token if allowed (for
                            permanent authentication) (used after expired token error)
    callback for requests:
        __call__(r)

    An instance of this class can be supplied to the SF database backend connection
    in order to customize default authentication. It will be saved to
        `connections['salesforce'].sf_session.auth`

        Use it typically at the beginning of Django request in your middleware by:
            connections['salesforce'].sf_session.auth.dynamic_start(access_token)

    http://docs.python-requests.org/en/latest/user/advanced/#custom-authentication
    """

    def __init__(self, db_alias, settings_dict=None, _session=None):
        """
        Set values for authentication
            Params:
                db_alias:  The database alias e.g. the default SF alias 'salesforce'.
                settings_dict: It is only important for the first connecting.
                        It should be taken from django.conf.DATABASES['salesforce'],
                        because it is not known initially in the connection.settings_dict.
                _session: Only for tests
        """
        self.db_alias = db_alias
        self.dynamic = None
        self.settings_dict = settings_dict or connections[db_alias].settings_dict
        self._session = _session or requests.Session()

    def authenticate(self):
        """
        Authenticate to the Salesforce API with the provided credentials.

        This function will be called only if a token is not in the cache.
        """
        raise NotImplementedError("The authenticate method should be subclassed.")

    def get_auth(self):
        """
        Cached value of authenticate() + the logic for the dynamic auth
        """
        if self.dynamic:
            return self.dynamic
        if self.settings_dict['USER'] == 'dynamic auth':
            return {'instance_url': self.settings_dict['HOST']}
        # If another thread is running inside this method, wait for it to
        # finish. Always release the lock no matter what happens in the block
        db_alias = self.db_alias
        with oauth_lock:
            if db_alias not in oauth_data:
                oauth_data[db_alias] = self.authenticate()
            return oauth_data[db_alias]

    def del_token(self):
        with oauth_lock:
            del oauth_data[self.db_alias]
        self.dynamic = None

    def __call__(self, r):
        """Standard auth hook on the "requests" request r"""
        access_token = self.get_auth()['access_token']
        r.headers['Authorization'] = 'OAuth %s' % access_token
        return r

    def reauthenticate(self):
        if self.dynamic is not None:
            # It is expected that with dynamic authentication we get a token that
            # is valid at least for a few future seconds, because we don't get
            # any password or permanent permission for it from the user.
            raise DatabaseError("Dynamically authenticated connection can never reauthenticate.")
        self.del_token()
        return self.get_auth()['access_token']

    @property
    def instance_url(self):
        return self.get_auth()['instance_url']

    def dynamic_start(self, access_token, instance_url=None, **kw):
        """
        Set the access token dynamically according to the current user.

        More parameters can be set.
        """
        self.dynamic = {'access_token': str(access_token), 'instance_url': str(instance_url)}
        self.dynamic.update(kw)

    def dynamic_end(self):
        """
        Clear the dynamic access token.
        """
        self.dynamic = None


class SalesforcePasswordAuth(SalesforceAuth):
    """
    Attaches "OAuth 2.0 Salesforce Password authentication" to the `requests` Session

    Static auth data are cached thread safely between threads. Thread safety
    is provided by the ancestor class.
    """
    def authenticate(self):
        """
        Authenticate to the Salesforce API with the provided credentials (password).
        """
        settings_dict = self.settings_dict
        url = ''.join([settings_dict['HOST'], '/services/oauth2/token'])

        log.info("attempting authentication to %s", settings_dict['HOST'])
        self._session.mount(settings_dict['HOST'], HTTPAdapter(max_retries=get_max_retries()))
        auth_params = {
            'grant_type':    'password',
            'client_id':     settings_dict['CONSUMER_KEY'],
            'client_secret': settings_dict['CONSUMER_SECRET'],
            'username':      settings_dict['USER'],
            'password':      settings_dict['PASSWORD'],
        }
        response = self._session.post(url, data=auth_params)
        if response.status_code == 200:
            # prefer str in Python 2 due to other API
            response_data = {str(k): str(v) for k, v in response.json().items()}
            # Verify signature (not important for this auth mechanism)
            calc_signature = (
                base64.b64encode(
                    hmac.new(
                        key=settings_dict['CONSUMER_SECRET'].encode('ascii'),
                        msg=(response_data['id'] + response_data['issued_at']).encode('ascii'),
                        digestmod=hashlib.sha256
                    ).digest()
                )
            ).decode('ascii')
            if calc_signature == response_data['signature']:
                log.info("successfully authenticated %s", settings_dict['USER'])
            else:
                raise IntegrityError('Invalid auth signature received')
        else:
            raise SalesforceAuthError("oauth failed: %s: %s" % (settings_dict['USER'], response.text))
        return response_data


class MockAuth(SalesforceAuth):
    """Dummy authentication for offline Mock tests"""
    def authenticate(self):
        return {'instance_url': 'mock://'}

    def get_auth(self):
        # this is never cached
        return self.authenticate()
