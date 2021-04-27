from django.contrib.auth import authenticate
from paramiko import ServerInterface, AUTH_SUCCESSFUL, OPEN_SUCCEEDED, AUTH_FAILED
from . import models
from .compat import get_username_field


class StubServer(ServerInterface):
    model = models.SFTPUserAccount
    username_field = get_username_field()
    username = None

    def check_auth_password(self, username, password):
        user = authenticate(
            **{self.username_field: username, 'password': password}
        )
        account = self.get_account(username)
        if not (user and account):
            return AUTH_FAILED
        self.username = username
        return AUTH_SUCCESSFUL

    def check_auth_publickey(self, username, key):
        return AUTH_FAILED

    def check_channel_request(self, kind, chanid):
        return OPEN_SUCCEEDED

    def get_allowed_auths(self, username):
        """List availble auth mechanisms."""
        return "password"

    def _filter_user_by(self, username):
        return {"user__%s" % self.username_field: username}

    def get_account(self, username):
        """return user by username.
        """
        try:
            account = self.model.objects.get(
                **self._filter_user_by(username)
            )
        except self.model.DoesNotExist:
            return None
        return account

    def get_home_dir(self, username=None):
        if not username:
            username = self.username
        account = self.get_account(username)
        if not account:
            return ''
        return account.get_home_dir()

