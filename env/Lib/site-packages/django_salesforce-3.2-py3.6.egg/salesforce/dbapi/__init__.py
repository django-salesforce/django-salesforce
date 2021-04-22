"""
simplified Python DB API 2.0 for Salesforce - (independent on Django)

A basic SQL SELECT and a small part of PEP 0249 will be implemented here.
Only SELECT command is currently implemented.
Transactions will be never implemented.
SQL commands INSERT and UPDATE could be implemented easily, but it is not
currently important because the current object implementation is good enough.

Purpose:
Splitting Django-Salesforce to a high level part that depends on Django
(especially on a Django version) and a low level part that depends
on Salesforce (but not on Django) has to be better for development,
maintenance and testing.
"""

from typing import Any
import logging
log = logging.getLogger(__name__)


# Dependencies of salesforce.dbapi on Django are tried to be minimalized.
# The biggest challenges are django.conf.settings, django.db.connections and django.test.
try:
    settings = None  # type: Any
    from django.conf import settings
    from django.db import connections as connections
except ImportError:
    # mock for some tests without a real Django
    import importlib
    import os
    from threading import local

    settings = importlib.import_module(os.environ['DJANGO_SETTINGS_MODULE'])

    if not getattr(settings, 'SF_CAN_RUN_WITHOUT_DJANGO', False):
        raise

    connections = local()


def get_max_retries() -> int:
    """Get the maximal number of requests retries

    The maximal number of retries for timeouts in requests to Force.com API.
    Can be set dynamically
    None: use defaults from settings.REQUESTS_MAX_RETRIES (default 1)
    0: no retry
    1: one retry
    """
    return getattr(settings, 'REQUESTS_MAX_RETRIES', 1)  # type: ignore[no-any-return] # noqa
