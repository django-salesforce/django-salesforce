from django.db import models, router
from django.utils.six import string_types

from salesforce.backend import manager, DJANGO_20_PLUS
from salesforce.backend.indep import get_sf_alt_pk
from salesforce.models import *  # NOQA; pylint:disable=wildcard-import,unused-wildcard-import
from salesforce.models import SalesforceAutoField, SalesforceModelBase, SF_PK, with_metaclass
from salesforce.router import is_sf_database


class SfCharAutoField(SalesforceAutoField):
    """Auto field that allows Salesforce ID or UUID in an alternate database"""

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
