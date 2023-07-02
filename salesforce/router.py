# django-salesforce
#
# by Hyneck Cernoch and Phil Christensen
# See LICENSE.md for details
#

"""
Database router for SalesforceModel objects.
"""

from typing import cast, Optional, Type
from django.apps import apps
from django.conf import settings
from django.db import models, DEFAULT_DB_ALIAS


def is_sf_database(db: Optional[str], model: Optional[models.Model] = None) -> bool:
    """The alias is a Salesforce database."""
    if db is None:
        return hasattr(model, '_salesforce_object')
    # simple check to prevent a possible circular dependency
    return 'salesforce' in settings.DATABASES[db]['ENGINE']


class ModelRouter:
    """
    Database router for Salesforce models.
    """
    # pylint:disable=protected-access
    @property
    def sf_alias(self) -> str:
        return cast(str, getattr(settings, 'SALESFORCE_DB_ALIAS', 'salesforce'))

    def db_for_read(self, model: models.Model, **hints: models.Model) -> Optional[str]:
        """
        If given some hints['instance'] that is saved in a db, use related
        fields from the same db. Otherwise if passed a class or instance to
        model, return the salesforce alias if it's a subclass of SalesforceModel.
        """
        if 'instance' in hints:
            db = hints['instance']._state.db
            if db:
                return db
        if hasattr(model, '_salesforce_object'):
            return self.sf_alias
        if model._meta.app_label == 'django_cache':
            return DEFAULT_DB_ALIAS
        return None

    def db_for_write(self, model: models.Model, **hints: models.Model) -> Optional[str]:
        """
        If given some hints['instance'] that is saved in a db, use related
        fields from the same db. Otherwise if passed a class or instance to
        model, return the salesforce alias if it's a subclass of SalesforceModel.
        """
        if 'instance' in hints:
            db = hints['instance']._state.db
            if db:
                return db
        if hasattr(model, '_salesforce_object'):
            return self.sf_alias
        if model._meta.app_label == 'django_cache':
            return DEFAULT_DB_ALIAS
        return None

    def allow_migrate(self, db: str, app_label: str, model_name: Optional[str] = None, **hints: Type[models.Model]
                      ) -> Optional[bool]:
        """
        Don't attempt to sync SF models to non SF databases and vice versa.
        """
        if model_name:
            try:
                model = apps.get_model(app_label, model_name)  # type: Optional[Type[models.Model]]
            except LookupError:
                # models that exist only in memory without 'models.py'
                if 'model' in hints and hints['model'].__module__ == '__fake__':
                    return None
                if 'model' in hints and hints['model']._meta.app_label == 'django_cache':
                    return db == DEFAULT_DB_ALIAS
                raise
        else:
            # hints are used with less priority, because many hints are dynamic
            # models made by migrations in a '__fake__' module which are not
            # SalesforceModels
            model = hints.get('model')

        if hasattr(model, '_salesforce_object'):
            # SF models can be migrated if SALESFORCE_DB_ALIAS is e.g.
            # a sqlite3 database or any non-SF database.
            if not (is_sf_database(db) or db == self.sf_alias):
                return False
        else:
            if is_sf_database(db) or self.sf_alias != DEFAULT_DB_ALIAS and db == self.sf_alias:
                return False
        # TODO: It is usual that "migrate" is currently disallowed for SF.
        # In the future it can be implemented to do a deep check by
        # introspection of compatibily between Django models and SF database.
        if hasattr(model, '_salesforce_object'):
            # return False
            pass
        # Nothing is decided about non SF models with non SF databases, because
        # it can be solved by other routers. Migration is enabled by default if
        # all routers return "None".
        return None
