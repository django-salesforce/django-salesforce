# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Django models for accessing Salesforce objects.

The Salesforce database is somewhat un-UNIXy or non-Pythonic, in that
column names are all in CamelCase. No attempt is made to work around this
issue, but normal use of `db_column` and `db_table` parameters should work.
"""

from __future__ import unicode_literals
import logging
import warnings

from django.db import models
from django.db.models.base import ModelBase
# Only these two `on_delete` options are currently supported
from django.db.models import PROTECT, DO_NOTHING  # NOQA
# from django.db.models import CASCADE, PROTECT, SET_NULL, SET, DO_NOTHING
from django.utils.six import with_metaclass, text_type

from salesforce.backend import manager
from salesforce.fields import SalesforceAutoField, SF_PK, SfField, ForeignKey
from salesforce.fields import DEFAULTED_ON_CREATE, NOT_UPDATEABLE, NOT_CREATEABLE, READ_ONLY
from salesforce.fields import *  # NOQA - imports for other modules
from salesforce import DJANGO_18_PLUS

__all__ = ('SalesforceModel', 'Model', 'DEFAULTED_ON_CREATE', 'PROTECT', 'DO_NOTHING', 'SF_PK', 'SfField',
           'NOT_UPDATEABLE, NOT_CREATEABLE, READ_ONLY')
log = logging.getLogger(__name__)


class SalesforceModelBase(ModelBase):
    """
    This is a sub-metaclass of the normal Django ModelBase.

    This metaclass overrides the default table-guessing behavior of Django
    and replaces it with code that defaults to the model name.
    """
    def __new__(cls, name, bases, attrs):
        attr_meta = attrs.get('Meta', None)
        if not DJANGO_18_PLUS and len(getattr(attr_meta, 'verbose_name', '')) > 39:
            attr_meta.verbose_name = attr_meta.verbose_name[:39]
        supplied_db_table = getattr(attr_meta, 'db_table', None)
        if getattr(attr_meta, 'dynamic_field_patterns', None):
            pattern_module, dynamic_field_patterns = getattr(attr_meta, 'dynamic_field_patterns')
            make_dynamic_fields(pattern_module, dynamic_field_patterns, attrs)
            delattr(attr_meta, 'dynamic_field_patterns')
        result = super(SalesforceModelBase, cls).__new__(cls, name, bases, attrs)
        if models.Model not in bases and supplied_db_table is None:
            result._meta.db_table = result._meta.concrete_model._meta.object_name
        return result

    def add_to_class(cls, name, value):
        if name == '_meta':
            sf_custom = False
            if hasattr(value.meta, 'custom'):
                sf_custom = value.meta.custom
                delattr(value.meta, 'custom')
            super(SalesforceModelBase, cls).add_to_class(name, value)
            setattr(cls._meta, 'sf_custom', sf_custom)
        else:
            if type(value) is models.manager.Manager:
                # TODO use args:  obj._constructor_args = (args, kwargs)
                value = manager.SalesforceManager()
            super(SalesforceModelBase, cls).add_to_class(name, value)


class SalesforceModel(with_metaclass(SalesforceModelBase, models.Model)):
    """
    Abstract model class for Salesforce objects.
    """
    _salesforce_object = True

    class Meta:
        managed = False
        abstract = True

    # Name of primary key 'Id' can be easily changed to 'id'
    # by "settings.SF_PK='id'".
    id = SalesforceAutoField(primary_key=True, name=SF_PK, db_column='Id',
                             verbose_name='ID', auto_created=True)


def make_dynamic_fields(pattern_module, dynamic_field_patterns, attrs):
    """Add some Salesforce fields from a pattern_module models.py

    Parameters:
        pattern_module:  Module where to search additional fields settings.
           It should be a models.py created by introspection (inspectdb)
           and should be a dummy app that is in INSTALLED_APPS. (That
           models.py is probably not a part of version control for you and
           is archived by an other way because the diff are huge. )
        dynamic_field_patterns:  List of regular expression for Salesforce
            field names that should be included automatically into the model.
        attrs:  Input/Output dictionary of model attributes. (no need to
            worry, added automatically)

    The patterns are applied sequentionally.
    If the pattern starts with "-" then the matched names are excluded.
    The search stops after the first match.
    A normal field that exists directly in a class is never rewritten
    by a dynamic field..
    All ForeingKey fields should be created explicitely. (For now to
    prevent possible issues and also for better readibility of the
    model. The automatic "dynamic" fields are intended especially for
    "maybe can be useful" fields and will work with ForeignKey in simple
    cases, e.g. without Proxy models etc. Works good for me.)

    This is useful for development: Many fields or all fields can be
    easily accessed by the model without a huge code. Finally
    all wildcard fields except the explicit names can be removed when
    the development is ready or .
    If you create migrations, you probably want to disable "dynamic_field_patterns"
    by setting them empty.

    Example:
        Meta:
            db_table = 'Contact'
            dynamic_patterns = exported.models, ['Last', '.*Date$']
    """
    import re
    attr_meta = attrs['Meta']
    db_table = getattr(attr_meta, 'db_table', None)
    if not db_table:
        raise RuntimeError('The "db_table" must be set in Meta if "dynamic_field_patterns" is used.')
    is_custom_model = getattr(attr_meta, 'custom', False)
    patterns = []
    for pat in dynamic_field_patterns:
        enabled = True
        if pat.startswith('-'):
            enabled = False
            pat = pat[1:]
        patterns.append((enabled, re.compile(r'^(?:{})$'.format(pat), re.I)))
    used_columns = []
    for name, attr in attrs.items():
        if isinstance(attr, SfField):
            field = attr
            if field.sf_custom is None and is_custom_model:
                field.sf_custom = True
            if not field.name:
                field.name = name
            attname, column = field.get_attname_column()
            used_columns.append(column)
    if pattern_module:
        for name, obj in vars(pattern_module).items():
            if not name.startswith('_'):
                if isinstance(obj, SalesforceModelBase) and getattr(obj._meta, 'db_table', None) == db_table:
                    cls = obj
                    break
        else:
            # not found db_table model, but decide between warning or exception
            if all(x.startswith('__') for x in dir(pattern_module)):
                warnings.warn("The module '%s' is empty. (It is OK if you are "
                              "rewriting new Models by pipe from inspectdb command.)"
                              % pattern_module.__name__)
                return
            else:
                raise RuntimeError("No Model for table '%s' found in the module '%s'"
                                   % (db_table, pattern_module.__name__))
    for field in cls._meta.fields:
        if not field.primary_key:
            attname, column = field.get_attname_column()
            for enabled, pat in patterns:
                if pat.match(column):
                    break
            else:
                enabled = False
            if enabled:
                if not isinstance(field, ForeignKey):
                    new_field = type(field)()
                    vars(new_field).update(vars(field))
                else:
                    # copy ForeignKey with target app changed to the current one
                    kw = {k: v for k, v in vars(field).items() if k in (
                        # universal options
                        'null', 'blank', 'choices', 'db_column', 'db_index', 'db_tablespace',
                        'default', 'editable', 'error_messages', 'help_text', 'primary_key', 'unique',
                        'unique_for_date', 'unique_for_month', 'unique_for_year', 'verbose_name',
                        'validators'
                        # foreign key options
                        'db_constraint', 'swappable',
                        # salesforce
                        'sf_read_only',
                    )}
                    new_field = type(field)(
                        field.rel.to if isinstance(field.rel.to, (str, text_type)) else field.rel.to.__name__,
                        on_delete=field.rel.on_delete,
                        to_field=field.rel.field_name,
                        related_name=field.rel.related_name,
                        related_query_name=field.rel.related_query_name,
                        custom=field.sf_custom,  # salesforce option
                        # ?? 'limit_choices_to', 'sf_namespace',
                        **kw)
                attrs[field.name] = new_field


Model = SalesforceModel
