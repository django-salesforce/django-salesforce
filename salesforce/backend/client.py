# django-salesforce
#
# by Hyneck Cernoch and Phil Christensen
# See LICENSE.md for details
#

"""
(empty) Module for command-line dbshell  (like django.db.backends.*.client)
"""

from django.core.exceptions import ImproperlyConfigured
from django.db.backends.base.client import BaseDatabaseClient


def complain(*args, **kwargs):
    raise ImproperlyConfigured("DatabaseClient: Not yet implemented for the Salesforce backend.")


class DatabaseClient(BaseDatabaseClient):
    runshell = complain

    @classmethod
    def settings_to_cmd_args_env(cls, settings_dict, parameters):
        complain()
