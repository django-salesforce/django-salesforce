"""
Module for models for a combined storage with a Salesforce and normal database.

usage e.g.:
  - Backup salesforce objects including its primary keys.
  - Use the backup in queries, including ForeignKeys related correctly to the same database.
  - Update the object in Salesfoce to the original values from backup object
    if the primary key still exists in salesforce.
  - Create a new non-salesforce object with an automatic uuid pk.
  - Use it as a much faster alternative than "data sandbox refresh".

The non-salesforce database uses a default uuid() key or a provided salesforce Id value.

The module less supported in future Django versions or unsupported.

Interesting not yet implemented ideas are:
  - Use a normal Salesforce backup zip like a read-only database (list
    of Salesforce objects that can be filtered and fast saved to a non-salesforce database
    by bulk_create().
  - Could be useful for tests with realistic data on a database with rollback.
"""

from django.db import models, router
from six import string_types

from salesforce.backend import manager, DJANGO_20_PLUS, DJANGO_30_PLUS
from salesforce.backend.indep import get_sf_alt_pk
from salesforce.models import *  # NOQA; pylint:disable=wildcard-import,unused-wildcard-import
from salesforce.models import SalesforceAutoField, SalesforceModelBase, SF_PK, with_metaclass
from salesforce.router import is_sf_database


class SfCharAutoField(SalesforceAutoField):
    """Auto field that allows Salesforce ID or UUID in an alternate database"""

    # db_returning = False  # this was a simple fix for Django >= 3.0,
    #                       # but a fix by "_do_insert()" is better.

    def get_internal_type(self):
        return None

    def db_type(self, connection):
        if connection.vendor != 'salesforce':
            # it is 'varchar(32)'
            return models.CharField(max_length=32).db_type(connection=connection)

    def rel_db_type(self, connection):
        if connection.vendor != 'salesforce':
            return models.CharField(max_length=32).db_type(connection=connection)


# pylint:disable=too-few-public-methods,function-redefined
class SalesforceModel(with_metaclass(SalesforceModelBase, models.Model)):
    """
    Abstract model class for Salesforce objects that can be saved to other db.

    (It is not a subclass of salesforce.models.SalesforceModel. That is not
    a big problem if we don't check inheritance but only the '_salesforce_object'
    attribute or if we use only this or only the original implementation.)
    """
    # pylint:disable=invalid-name
    _salesforce_object = 'extended'
    objects = manager.SalesforceManager()

    class Meta:
        # pylint:disable=duplicate-code
        abstract = True
        base_manager_name = 'objects'
        if not DJANGO_20_PLUS:
            manager_inheritance_from_future = True

    id = SfCharAutoField(primary_key=True, name=SF_PK, db_column='Id', verbose_name='ID', auto_created=True)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        using = using or router.db_for_write(self.__class__, instance=self)
        if self.pk is None and not force_update and not is_sf_database(using):
            self.pk = get_sf_alt_pk()
        super(SalesforceModel, self).save(force_insert=force_insert, force_update=force_update,
                                          using=using, update_fields=update_fields)
        if not isinstance(self.pk, string_types):
            raise ValueError("The primary key value is not assigned correctly")

    if DJANGO_30_PLUS:

        def _do_insert(self, manager, using, fields, returning_fields, raw):
            # the check "is_sf_database(using)" is used for something unexpected
            if self.pk and not is_sf_database(using):
                returning_fields = []
            return super(SalesforceModel, self)._do_insert(manager, using, fields, returning_fields, raw)
