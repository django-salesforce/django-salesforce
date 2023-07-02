# django-salesforce
#
# by Hyneck Cernoch and Phil Christensen
# See LICENSE.md for details
#

"""
Default validation code.  (like django.db.backends.*.validation)
"""
from typing import Any, List
from django.core.management import ManagementUtility
from django.core import checks
from django.conf import settings
from django.db import connections, router as django_router
from django.db.backends.base.validation import BaseDatabaseValidation
import requests.exceptions
from salesforce.backend import enterprise
from salesforce.dbapi.exceptions import LicenseError, SalesforceError
from salesforce.models import SalesforceModel
from salesforce.router import is_sf_database


class DatabaseValidation(BaseDatabaseValidation):
    def check(self, **kwargs) -> List[Any]:
        issues = super().check(**kwargs)
        issues.extend(self.check_standard_install(**kwargs))
        return issues

    def check_standard_install(self, **kwargs) -> List[Any]:
        issues = []

        # check license (must be checked before check connection to prevent false positive)
        try:
            enterprise.check_license_in_latest_django()
        except LicenseError:
            issues.append(
                checks.Warning(
                    "DJSF_LICENSE_KEY is necessary for django-salesforce with the newest Django version",
                    hint='You can become a sponsor to get it or you can use our equivalent package '
                    "django-salesforce-agpl if an AGPL license is acceptable for you.",
                    id="salesforce.W005",  # i.e paragraph 5 in README
                )
            )
        else:
            # check connection
            if not getattr(settings, 'SF_LAZY_CONNECT', False):
                alias = self.connection.alias
                try:
                    connections[alias].cursor()
                except (SalesforceError, requests.exceptions.ConnectionError) as exc:
                    issues.append(
                        checks.Warning(
                            f"Can not connect to a Salesforce database '{alias}'",
                            hint=repr(exc),
                            id="salesforce.W002",
                        )
                    )

        # check the database router
        maybe_non_sf_test = (getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce') == 'default' and
                             settings.DATABASES['default']['ENGINE'] != 'salesforce.backend')
        if not is_sf_database(django_router.db_for_read(SalesforceModel)) and not maybe_non_sf_test:
            issues.append(
                checks.Warning(
                    "Tables with SalesforceModel are not routed to a Salesforce database",
                    hint='add settings DATABASE_ROUTERS = ["salesforce.router.ModelRouter"]  # (README 3)',
                    id="salesforce.W003",
                )
            )

        # check requirements for inspectdb (i.e. "salesforce" in INSTALLED_APPS)
        if 'salesforce' not in ManagementUtility(['', '']).fetch_command('inspectdb').__module__:
            issues.append(
                checks.Warning(
                    "The command 'inspectdb' would not work correctly with Salesforce databases",
                    hint='add "salesforce" to INSTALLED_APPS (README 4)',
                    id="salesforce.W004",
                )
            )

        return issues
