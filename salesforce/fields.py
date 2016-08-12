# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Adds support for Salesforce primary keys.
"""

import warnings
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext_lazy as _
from django.db.models import fields
from django.db.models import PROTECT, DO_NOTHING  # NOQA
from django.db import models
from django.utils.encoding import smart_text
from django.utils.six import string_types

from salesforce import DJANGO_19_PLUS
from salesforce.backend.operations import DefaultedOnCreate

# None of field types defined in this module need a "deconstruct" method,
# in Django 1.7+, because their parameters only describe fixed nature of SF
# standard objects that can not be modified no ways by no API or spell.

FULL_WRITABLE  = 0
NOT_UPDATEABLE = 1
NOT_CREATEABLE = 2
READ_ONLY = 3  # (NOT_UPDATEABLE & NOT_CREATEABLE)
DEFAULTED_ON_CREATE = DefaultedOnCreate()

SF_PK = getattr(settings, 'SF_PK', 'id')
if not SF_PK in ('id', 'Id'):
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

    def to_python(self, value):
        if isinstance(value, string_types) or value is None:
            return value
        return smart_text(value)

    def get_prep_value(self, value):
        return self.to_python(value)

    def contribute_to_class(self, cls, name):
        name = name if self.name is None else self.name
        # we can't require "self.auto_created==True" due to backward compatibility
        # with old migrations created before v0.6. Other conditions are enough.
        if name != SF_PK or not self.primary_key:
            raise ImproperlyConfigured("SalesforceAutoField must be a primary"
                    "key with the name '%s' (as configured by settings)." % SF_PK)
        if cls._meta.has_auto_field:
            if (type(self) == type(cls._meta.auto_field) and self.model._meta.abstract and
                    cls._meta.auto_field.name == SF_PK):
                # Creating the Model that inherits fields from more abstract classes
                # with the same default SalesforceAutoFieldy The second one can be
                # ignored.
                return
            else:
                raise ImproperlyConfigured("The model %s can not have more than one AutoField, "
                        "but currently: (%s=%s, %s=%s)"
                        % (cls, cls._meta.auto_field.name, cls._meta.auto_field, name, self))
        super(SalesforceAutoField, self).contribute_to_class(cls, name)
        cls._meta.has_auto_field = True
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
        super(SfField, self).__init__(*args, **kwargs)

    def get_attname_column(self):
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

    def contribute_to_class(self, cls, name, **kwargs):
        super(SfField, self).contribute_to_class(cls, name, **kwargs)
        if self.sf_custom is None and hasattr(cls._meta, 'sf_custom'):
            # Only custom fields in models explicitly marked by
            # Meta custom=True are recognized automatically - for
            # backward compatibility reasons.
            self.sf_custom = cls._meta.sf_custom
        if self.sf_custom and '__' in cls._meta.db_table[:-3]:
            self.sf_namespace = cls._meta.db_table.split('__')[0] + '__'
        self.set_attributes_from_name(name)


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
class SmallIntegerField(SfField, models.SmallIntegerField):
    """SmallIntegerField with sf_read_only attribute for Salesforce."""
    pass
class BooleanField(SfField, models.BooleanField):
    """BooleanField with sf_read_only attribute for Salesforce."""
    def __init__(self, default=False, **kwargs):
        super(BooleanField, self).__init__(default=default, **kwargs)

    def to_python(self, value):
        if isinstance(value, DefaultedOnCreate):
            return value
        else:
            return super(BooleanField, self).to_python(value)


class DecimalField(SfField, models.DecimalField):
    """DecimalField with sf_read_only attribute for Salesforce."""
    def to_python(self, value):
        if str(value) == 'DEFAULTED_ON_CREATE':
            return value
        return super(DecimalField, self).to_python(value)


class DateTimeField(SfField, models.DateTimeField):
    """DateTimeField with sf_read_only attribute for Salesforce."""
    pass
class DateField(SfField, models.DateField):
    """DateField with sf_read_only attribute for Salesforce."""
    pass
class TimeField(SfField, models.TimeField):
    """TimeField with sf_read_only attribute for Salesforce."""
    pass


class ForeignKey(SfField, models.ForeignKey):
    """ForeignKey with sf_read_only attribute and acceptable by Salesforce."""
    def __init__(self, *args, **kwargs):
        # Checks parameters before call to ancestor.
        if DJANGO_19_PLUS and args[1:2]:
            on_delete = args[1].__name__
        else:
            on_delete = kwargs.get('on_delete', models.CASCADE).__name__
        if not on_delete in ('PROTECT', 'DO_NOTHING'):
            # The option CASCADE (currently fails) would be unsafe after a fix
            # of on_delete because Cascade delete is not usually enabled in SF
            # for safety reasons for most fields objects, namely for Owner,
            # CreatedBy etc. Some related objects are deleted automatically
            # by SF even with DO_NOTHING in Django, e.g. for
            # Campaign/CampaignMember
            related_object = args[0]
            warnings.warn("Only foreign keys with on_delete = PROTECT or "
                    "DO_NOTHING are currently supported, not %s related to %s"
                    % (on_delete, related_object))
        super(ForeignKey, self).__init__(*args, **kwargs)

    def get_attname(self):
        if self.name.islower():
            # the same as django.db.models.fields.related.ForeignKey.get_attname
            return '%s_id' % self.name
        else:
            return '%sId' % self.name

    def get_attname_column(self):
        attname, column = super(ForeignKey, self).get_attname_column()
        if self.db_column is None and not self.sf_custom:
            column += 'Id'
        return attname, column


class OneToOneField(ForeignKey, models.OneToOneField):
    """OneToOneField with sf_read_only attribute and acceptable by Salesforce."""
    pass


AutoField = SalesforceAutoField
