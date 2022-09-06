import re
import threading
import time
from typing import Any, cast, Callable, Dict, Optional

# Dependencies of salesforce.dbapi on Django are minimalized.
# The biggest challenges are django.conf.settings, django.db.connections and django.test.

try:
    settings = None  # type: Any
    from django.conf import settings
except ImportError:
    # mock for some tests without a real Django
    import importlib
    import os

    settings = importlib.import_module(os.environ['DJANGO_SETTINGS_MODULE'])

    if not getattr(settings, 'SF_CAN_RUN_WITHOUT_DJANGO', False):
        raise


def get_max_retries() -> int:
    """Get the maximal number of requests retries

    The maximal number of retries for timeouts in requests to Force.com API.
    Can be set dynamically
    None: use defaults from settings.REQUESTS_MAX_RETRIES (default 1)
    0: no retry
    1: one retry
    """
    return getattr(settings, 'REQUESTS_MAX_RETRIES', 1)  # type: ignore[no-any-return] # noqa


def get_thread_connections() -> Dict[Optional[str], Any]:
    if not hasattr(thread_loc, 'connections'):
        thread_loc.connections = {}
    return cast(Dict[Optional[str], Any], thread_loc.connections)


class TimeStatistics:

    def __init__(self, expiration: float = 300) -> None:
        self.expiration = expiration
        self.data = {}  # type: Dict[str, float]

    def update_callback(self, url: str, callback: Optional[Callable[[], Any]] = None) -> None:
        """Update the statistics for the domain"""
        domain = self.domain(url)
        last_req = self.data.get(domain, 0)
        t_new = time.time()
        do_call = (t_new - last_req > self.expiration)
        self.data[domain] = t_new
        if do_call and callback:
            callback()

    @staticmethod
    def domain(url: str) -> str:
        match = re.match(r'^(?:https|mock)://([^/]*)/?', url)
        assert match, "HOST must be including the protocol and :// like 'https://login.salesforce.com'"
        return match.groups()[0]


time_statistics = TimeStatistics(300)
thread_loc = threading.local()
