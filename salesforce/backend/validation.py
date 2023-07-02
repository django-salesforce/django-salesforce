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
from requests.exceptions import ConnectionError
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

        alias = self.connection.alias
        try:
            connections[alias].cursor()
        except LicenseError:
            issues.append(
                checks.Warning(
                    "DJSF_LICENSE_KEY is necessary for django-salesforce with the newest Django version",
                    hint='You can become a sponsor to get it or you can use our equivalent package '
                    "django-salesforce-agpl if an AGPL license is acceptable for you.",
                    id="salesforce.W005",
                )
            )
        except (SalesforceError, ConnectionError) as exc:
            issues.append(
                checks.Warning(
                    f"Can not connect to a Salesforce database '{alias}'",
                    hint=repr(exc),
                )
            )

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

        if 'salesforce' not in ManagementUtility(['', '']).fetch_command('inspectdb').__module__:
            issues.append(
                checks.Warning(
                    "The command 'inspectdb' would not work correctly with Salesforce databases",
                    hint='add "salesforce" to INSTALLED_APPS (README 4)',
                    id="salesforce.W004",
                )
            )

        return issues
