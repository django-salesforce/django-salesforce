# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Customized fields for Salesforce, especially the primary key. (like django.db.models.fields)
"""

from typing import Tuple
import typing
import warnings
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from django.db.models import fields
from django.db.models import PROTECT, DO_NOTHING  # NOQA pylint:disable=unused-import
from django.db import models

from salesforce.defaults import DEFAULTED_ON_CREATE, DefaultedOnCreate

# None of field types defined here don't need a "deconstruct" method.
# Their parameters only describe the different, but stable nature of SF standard objects.

FULL_WRITABLE = 0
NOT_UPDATEABLE = 1
NOT_CREATEABLE = 2
READ_ONLY = 3  # (NOT_UPDATEABLE & NOT_CREATEABLE)

SF_PK = getattr(settings, 'SF_PK', 'id')
if SF_PK not in ('id', 'Id'):
    raise ImproperlyConfigured("Value of settings.SF_PK must be 'id' or 'Id' or undefined.")


class SalesforceAutoField(fields.AutoField):
    """
    An AutoField that works with Salesforce primary keys.

    It is used by SalesforceModel as a custom primary key. It doesn't convert
    its value to int.
    """
    description = _("Text")

    default_error_messages = {
        'invalid': _('This value must be a valid Salesforce ID.'),
    }

    def __init__(self, *args, **kwargs):
        # The parameter 'sf_read_only' is not used normally, maybe only if someone
        # added SalesforceAutoFields to the Model manually
        kwargs.pop('sf_read_only', None)
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, str) or value is None:
            return value
        return str(value)

    def get_prep_value(self, value):
        return self.to_python(value)

    def contribute_to_class(self, cls, name, **kwargs):
        name = name if self.name is None else self.name
        # we can't require "self.auto_created==True" due to backward compatibility
        # with old migrations created before v0.6. Other conditions are enough.
        if name != SF_PK or not self.primary_key:
            raise ImproperlyConfigured(
                "SalesforceAutoField must be a primary key"
                "with the name '%s' (configurable by settings)." % SF_PK)
        if cls._meta.auto_field:
            # pylint:disable=unidiomatic-typecheck
            if not (type(self) == type(cls._meta.auto_field) and self.model._meta.abstract and  # NOQA type eq
                    cls._meta.auto_field.name == SF_PK):
                raise ImproperlyConfigured(
                    "The model %s can not have more than one AutoField, "
                    "but currently: (%s=%s, %s=%s)" % (
                        cls,
                        cls._meta.auto_field.name, cls._meta.auto_field,
                        name, self
                    )
                )
            # A model is created  that inherits fields from more abstract classes
            # with the same default SalesforceAutoField. Therefore the second should be
            # ignored.
            return
        super(SalesforceAutoField, self).contribute_to_class(cls, name, **kwargs)
        cls._meta.auto_field = self


class SfField(models.Field):
    """
    Add support of 'sf_read_only' and 'custom' parameters to Salesforce fields.

        sf_read_only=3 (READ_ONLY):  The field can not be specified neither on insert or update.
            e.g. LastModifiedDate (the most frequent type of read only)
        sf_read_only=1 (NOT_UPDATEABLE):  The field can be specified on insert but can not be later never modified.
            e.g. ContactId in User object (relative frequent)
        sf_read_only=2 (NOT_CREATEABLE):  The field can not be specified on insert but can be later modified.
            e.g. RecordType.IsActive or Lead.EmailBouncedReason
        sf_read_only=0:  normal writable (default)

        custom=True : Add '__c' to the column name if no db_column is defined.
    """
    def __init__(self, *args, **kwargs):
        self.sf_read_only = kwargs.pop('sf_read_only', 0)
        self.sf_custom = kwargs.pop('custom', None)
        self.sf_namespace = ''
        if kwargs.get('default') is DEFAULTED_ON_CREATE:
            kwargs['default'] = DefaultedOnCreate(internal_type=self.get_internal_type())
        super(SfField, self).__init__(*args, **kwargs)

    def get_attname_column(self) -> Tuple[str, str]:
        """
        Get the database column name automatically in most cases.
        """
        # See "A guide to Field parameters": django/db/models/fields/__init__.py
        #   * attname:   The attribute to use on the model object. This is the same as
        #                "name", except in the case of ForeignKeys, where "_id" is
        #                appended.
        #   * column:    The database column for this field. This is the same as
        #                "attname", except if db_column is specified.
        attname = self.get_attname()
        if self.db_column is not None:
            # explicit name
            column = self.db_column
        else:
            if not self.name.islower():
                # a Salesforce style name e.g. 'LastName' or 'MyCustomField'
                column = self.name
            else:
                # a Django style name like 'last_name' or 'my_custom_field'
                column = self.name.title().replace('_', '')
            # Fix custom fields
            if self.sf_custom:
                column = self.sf_namespace + column + '__c'
        return attname, column

    def contribute_to_class(self, cls, name, private_only=False, **kwargs):
        # More arguments are in Django 1.11 than in Django 2.0, therefore we use the universal **kwargs
        # pylint:disable=arguments-differ
        super(SfField, self).contribute_to_class(cls, name, private_only=private_only, **kwargs)
        if self.sf_custom is None and hasattr(cls._meta, 'sf_custom'):
            # Only custom fields in models explicitly marked by
            # Meta custom=True are recognized automatically - for
            # backward compatibility reasons.
            self.sf_custom = cls._meta.sf_custom
        if self.sf_custom and '__' in cls._meta.db_table[:-3]:
            self.sf_namespace = cls._meta.db_table.split('__')[0] + '__'
        self.set_attributes_from_name(name)

# pylint:disable=unnecessary-pass,too-many-ancestors


class CharField(SfField, models.CharField):
    """CharField with sf_read_only attribute for Salesforce."""
    pass


class EmailField(SfField, models.EmailField):
    """EmailField with sf_read_only attribute for Salesforce."""
    pass


class URLField(SfField, models.URLField):
    """URLField with sf_read_only attribute for Salesforce."""
    pass


class TextField(SfField, models.TextField):
    """TextField with sf_read_only attribute for Salesforce."""
    pass


class IntegerField(SfField, models.IntegerField):
    """IntegerField with sf_read_only attribute for Salesforce."""
    pass


class BigIntegerField(SfField, models.BigIntegerField):
    """BigIntegerField with sf_read_only attribute for Salesforce."""
    # important for other database backends, e.g. in tests
    # The biggest exact value is +-(2 ** 53 -1 ), approx. 9.007E15
    pass


class SmallIntegerField(SfField, models.SmallIntegerField):
    """SmallIntegerField with sf_read_only attribute for Salesforce."""
    pass


class DecimalField(SfField, models.DecimalField):
    """
    DecimalField with sf_read_only attribute for Salesforce.

    Salesforce has only one numeric type xsd:double, but no integer.
    Even a numeric field with declared zero decimal_places can contain
    pi=3.14159265358979 in the database accidentally, but if also the value
    is integer,then it is without '.0'.
    DecimalField is the default numeric type used by itrospection inspectdb.
    """
    def to_python(self, value):
        if str(value) == '':
            return value
        ret = super(DecimalField, self).to_python(value)
        if ret is not None and self.decimal_places == 0:
            # this is because Salesforce has no numeric integer type
            if ret == int(ret):
                ret = Decimal(int(ret))
        return ret

    # parameter "context" is for Django <= 1.11 (the same is in more classes here)
    def from_db_value(self, value, expression, connection, context=None):
        # pylint:disable=unused-argument
        # TODO refactor and move to the driver like in other backends
        if isinstance(value, float):
            value = str(value)
        return self.to_python(value)


class FloatField(SfField, models.FloatField):
    """FloatField for Salesforce.

    It is Float in Python and the same as DecimalField in the database.
    """
    pass


class BooleanField(SfField, models.BooleanField):
    """BooleanField with sf_read_only attribute for Salesforce.

    No NullBooleanField exist for Salesforce and every BooleanField has
    a default value. Implicit default is False if not specified.
    """
    def __init__(self, default=False, **kwargs):
        super(BooleanField, self).__init__(default=default, **kwargs)


class DateTimeField(SfField, models.DateTimeField):
    """DateTimeField with sf_read_only attribute for Salesforce."""


class DateField(SfField, models.DateField):
    """DateField with sf_read_only attribute for Salesforce."""

    def from_db_value(self, value, expression, connection, context=None):
        # pylint:disable=unused-argument
        return self.to_python(value)


class TimeField(SfField, models.TimeField):
    """TimeField with sf_read_only attribute for Salesforce."""

    def from_db_value(self, value, expression, connection, context=None):
        # pylint:disable=unused-argument
        return self.to_python(value)


if typing.TYPE_CHECKING:
    # static typing of a mixin requires an additional base, that is not necessary
    # at runtime
    _MixinTypingBase = models.ForeignObject
else:
    _MixinTypingBase = object


class SfForeignObjectMixin(SfField, _MixinTypingBase):
    def __init__(self, to, on_delete, *args, **kwargs):
        # Checks parameters before call to ancestor.
        if on_delete.__name__ not in ('PROTECT', 'DO_NOTHING'):
            # The option CASCADE (currently fails) would be unsafe after a fix
            # of on_delete because Cascade delete is not usually enabled in SF
            # for safety reasons for most fields objects, namely for Owner,
            # CreatedBy etc. Some related objects are deleted automatically
            # by SF even with DO_NOTHING in Django, e.g. for
            # Campaign/CampaignMember
            warnings.warn(
                "Only foreign keys with on_delete = PROTECT or "
                "DO_NOTHING are currently supported, not %s related to %s"
                % (on_delete, to))
        super().__init__(to, on_delete, *args, **kwargs)

    def get_attname(self) -> str:
        if self.name.islower():  # pylint:disable=no-else-return
            # the same as django.db.models.fields.related.ForeignKey.get_attname
            return '%s_id' % self.name
        else:
            return '%sId' % self.name

    def get_attname_column(self) -> Tuple[str, str]:
        attname, column = super().get_attname_column()
        if self.db_column is None and not self.sf_custom:
            column += 'Id'
        return attname, column


class ForeignKey(SfForeignObjectMixin, models.ForeignKey):
    """ForeignKey with sf_read_only attribute that is acceptable by Salesforce."""


class OneToOneField(SfForeignObjectMixin, models.OneToOneField):
    """OneToOneField with sf_read_only attribute that is acceptable by Salesforce."""


class XJSONField(TextField):  # type: ignore[no-redef] # noqa
    """
    Salesforce internal "complexvalue" field similar to JSON, used by SFDC for metadata,

    this field should not be used for normal data or with other database backends.
    """

    def get_internal_type(self):
        return "TextField"

    def get_prep_value(self, value):
        return value

    def to_python(self, value):
        return value


AutoField = SalesforceAutoField
