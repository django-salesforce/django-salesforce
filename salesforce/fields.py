# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Customized fields for Salesforce, especially the primary key. (like django.db.models.fields)
"""

from typing import Any, Callable, Optional, Tuple, Type, TYPE_CHECKING, Union
import warnings
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _
from django.db.backends.base.base import BaseDatabaseWrapper as DatabaseWrapper
from django.db.models import fields
from django.db.models import PROTECT, DO_NOTHING  # NOQA pylint:disable=unused-import
from django.db import models

from salesforce.defaults import DEFAULTED_ON_CREATE, DefaultedOnCreate, BaseDefault


# None of field types defined here don't need a "deconstruct" method.
# Their parameters only describe the different, but stable nature of SF standard objects.

FULL_WRITABLE = 0
NOT_UPDATEABLE = 1
NOT_CREATEABLE = 2
READ_ONLY = 3  # (NOT_UPDATEABLE & NOT_CREATEABLE)

SF_PK = getattr(settings, 'SF_PK', 'id')
if SF_PK not in ('id', 'Id'):
    raise ImproperlyConfigured("Value of settings.SF_PK must be 'id' or 'Id' or undefined.")

STANDARD_FIELDS = {
    x.lower() for x in (
        'Id',
        'Name',
        'RecordType',
        'CreatedDate',
        'CreatedBy',
        'LastModifiedDate',
        'LastModifiedBy',
        'SystemModstamp',
        'LastActivityDate',
        'LastViewdDate',
        'LastReferencedDate',
        'IsDeleted',
    )
}


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
    # the model can be managed by Django also in SFDC databases if 'self.sf_managed_model = True'
    sf_managed_model = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # The parameter 'sf_read_only' is not used normally, maybe only if someone
        # added SalesforceAutoFields to the Model manually
        kwargs.pop('sf_read_only', None)
        self.sf_managed = False
        self.sf_managed_model = kwargs.pop('sf_managed_model', False)
        super().__init__(*args, **kwargs)

    def to_python(self, value: Any) -> Optional[str]:
        if isinstance(value, str) or value is None:
            return value
        return str(value)

    def get_prep_value(self, value: Any) -> Any:
        return self.to_python(value)

    def contribute_to_class(self, cls: Type[models.Model], name: str,  # noqa pylint:disable=arguments-differ
                            private_only: bool = False) -> None:
        name = name if self.name is None else self.name
        # we can't require "self.auto_created==True" due to backward compatibility
        # with old migrations created before v0.6. Other conditions are enough.
        if name != SF_PK or not self.primary_key:
            raise ImproperlyConfigured(
                "SalesforceAutoField must be a primary key"
                "with the name '%s' (configurable by settings)." % SF_PK)
        if cls._meta.auto_field:
            # A model has another auto_field yet and a new auto field is added.
            same_type = type(self) == type(cls._meta.auto_field)  # noqa pylint:disable=unidiomatic-typecheck
            # If the previous auto field was created automatically by inheritation from more abstract classes
            # then it is OK and ignore it. In all other cases it is error.
            if same_type and self.model._meta.abstract and cls._meta.auto_field.name == SF_PK:
                return
            raise ImproperlyConfigured(
                "The model %s can not have more than one AutoField, "
                "but currently: (%s=%s, %s=%s)" % (
                    cls,
                    cls._meta.auto_field.name, cls._meta.auto_field,
                    name, self
                )
            )
        if getattr(cls._meta, 'sf_managed', False):
            self.sf_managed_model = True
        super().contribute_to_class(cls, name, private_only=private_only)
        cls._meta.auto_field = self

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.db_column == 'Id' and 'db_column' in kwargs:
            del kwargs['db_column']
        if self.sf_managed_model:
            kwargs['sf_managed_model'] = True
        return name, path, args, kwargs


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
    column = None  # type: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.sf_read_only = kwargs.pop('sf_read_only', 0)   # type: int
        self.sf_custom = kwargs.pop('custom', None)         # type: Optional[bool]
        self.sf_namespace = kwargs.pop('sf_namespace', '')  # type: str
        self.sf_managed = kwargs.pop('sf_managed', None)    # type: Optional[bool]

        assert (self.sf_custom is None or kwargs.get('db_column') is None or
                self.sf_custom == kwargs['db_column'].endswith('__c'))
        assert not self.sf_namespace or self.sf_custom is not False
        if kwargs.get('default') is DEFAULTED_ON_CREATE:
            kwargs['default'] = DefaultedOnCreate(internal_type=self.get_internal_type())
        super().__init__(*args, **kwargs)

    def deconstruct(self) -> Tuple[Any, Any, Any, Any]:
        name, path, args, kwargs = super().deconstruct()
        if self.name:
            policy = 'minimal'
            _, column = self.get_attname_column()
            if '__' in column or policy != 'minimal':
                kwargs['db_column'] = column
            else:
                tmp_db_column = self.db_column
                self.db_column = None
                _, auto_db_column = self.get_attname_column()
                self.db_column = tmp_db_column

                if column != auto_db_column:
                    kwargs['db_column'] = column
                elif 'db_column' in kwargs:
                    del kwargs['db_column']
        if self.sf_managed is not None:
            kwargs['sf_managed'] = self.sf_managed
        return name, path, args, kwargs

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
                column = column + '__c'
                if self.sf_namespace:
                    column = self.sf_namespace + '__' + column
        return attname, column

    def contribute_to_class(self, cls: Type[models.Model], name: str, private_only: bool = False) -> None:
        super().contribute_to_class(cls, name, private_only=private_only)
        is_custom_model = getattr(cls._meta, 'sf_custom', False)
        if self.sf_custom is None and is_custom_model and self.column.lower() not in STANDARD_FIELDS:
            # Automatically recognized custom fields can be only in custom models explicitly marked by Meta custom=True
            # are recognized automatically - for
            # backward compatibility reasons.
            self.sf_custom = True
            # set an empty value to be fixed on the next line
            self.column = ''
        self.set_attributes_from_name(name)
        column = self.column
        assert column
        sf_managed_model = getattr(cls._meta, 'sf_managed', False)
        if self.sf_managed is None and sf_managed_model and self.column and column.endswith('__c'):
            self.sf_managed = True


# pylint:disable=unnecessary-pass,too-many-ancestors


class CharField(SfField, models.CharField):
    """CharField with sf_read_only attribute for Salesforce."""

    def db_type(self, connection: Any) -> str:
        return 'Text' if not self.choices else 'PickList'


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
    def to_python(self, value: Any) -> Any:
        if str(value) == '':
            return value
        ret = super().to_python(value)
        if ret is not None and self.decimal_places == 0:
            # this is because Salesforce has no numeric integer type
            if ret == int(ret):
                ret = Decimal(int(ret))
        return ret

    def from_db_value(self, value: Any, expression: Any, connection: DatabaseWrapper) -> Any:
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

    Every BooleanField has a default value. It is False if default
    value checkbox is unchecked or True if checked.
    No NullBooleanField exist for Salesforce.
    """
    def __init__(self, default: Union[bool, BaseDefault] = False, **kwargs: Any) -> None:
        super().__init__(default=default, **kwargs)


class DateTimeField(SfField, models.DateTimeField):
    """DateTimeField with sf_read_only attribute for Salesforce."""


class DateField(SfField, models.DateField):
    """DateField with sf_read_only attribute for Salesforce."""

    def from_db_value(self, value: Any, expression: Any, connection: DatabaseWrapper) -> Any:
        # pylint:disable=unused-argument
        return self.to_python(value)


class TimeField(SfField, models.TimeField):
    """TimeField with sf_read_only attribute for Salesforce."""

    def from_db_value(self, value: Any, expression: Any, connection: DatabaseWrapper) -> Any:
        # pylint:disable=unused-argument
        return self.to_python(value)


if TYPE_CHECKING:
    # static typing of a mixin requires an additional base, that is not necessary
    # at runtime
    _MixinTypingBase = models.ForeignObject
else:
    _MixinTypingBase = object


class SfForeignObjectMixin(SfField, _MixinTypingBase):
    def __init__(self, to: Union[Type[models.Model], str], on_delete: Callable[..., None], *args: Any, **kwargs: Any
                 ) -> None:
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

    def db_type(self, connection: Any) -> str:
        if connection.vendor == 'salesforce':
            return 'Lookup'
        return super().db_type(connection)


class OneToOneField(SfForeignObjectMixin, models.OneToOneField):
    """OneToOneField with sf_read_only attribute that is acceptable by Salesforce."""

    def db_type(self, connection: Any) -> str:
        if connection.vendor == 'salesforce':
            return 'Lookup'
        return super().db_type(connection)


class XJSONField(TextField):
    """
    Salesforce internal "complexvalue" field similar to JSON, used by SFDC for metadata,

    this field should not be used for normal data or with other database backends.
    """

    def get_internal_type(self) -> str:
        return "TextField"

    def get_prep_value(self, value: Any) -> Any:
        return value

    def to_python(self, value: Any) -> Any:
        return value


AutoField = SalesforceAutoField
