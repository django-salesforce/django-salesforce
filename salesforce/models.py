# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Django models for accessing Salesforce objects. (like django.db.models)

The Salesforce database is somewhat un-UNIXy or non-Pythonic, in that
column names are all in CamelCase. No attempt is made to work around this
issue, but normal use of `db_column` and `db_table` parameters should work.
"""

from __future__ import unicode_literals
from inspect import isclass
import logging
import warnings

from django.db import models
from django.db.models.base import ModelBase
# Only these two `on_delete` options are currently supported
from django.db.models import PROTECT, DO_NOTHING  # NOQA pylint:disable=unused-wildcard-import,wildcard-import
# from django.db.models import CASCADE, PROTECT, SET_NULL, SET, DO_NOTHING
from six import with_metaclass

from salesforce.backend import manager, DJANGO_20_PLUS
from salesforce.fields import SalesforceAutoField, SF_PK, SfField, ForeignKey
from salesforce.fields import DEFAULTED_ON_CREATE, NOT_UPDATEABLE, NOT_CREATEABLE, READ_ONLY
from salesforce.fields import *  # NOQA pylint:disable=unused-wildcard-import,wildcard-import
from salesforce.backend.indep import LazyField

__all__ = ('SalesforceModel', 'Model', 'DEFAULTED_ON_CREATE', 'PROTECT', 'DO_NOTHING', 'SF_PK', 'SfField',
           'NOT_UPDATEABLE', 'NOT_CREATEABLE', 'READ_ONLY')

log = logging.getLogger(__name__)


class SalesforceModelBase(ModelBase):
    """
    This is a sub-metaclass of the normal Django ModelBase.

    This metaclass overrides the default table-guessing behavior of Django
    and replaces it with code that defaults to the model name.
    """
    def __new__(cls, name, bases, attrs, **kwargs):
        attr_meta = attrs.get('Meta', None)
        supplied_db_table = getattr(attr_meta, 'db_table', None)
        if getattr(attr_meta, 'dynamic_field_patterns', None):
            pattern_module, dynamic_field_patterns = getattr(attr_meta, 'dynamic_field_patterns')
            make_dynamic_fields(pattern_module, dynamic_field_patterns, attrs)
            delattr(attr_meta, 'dynamic_field_patterns')
        result = super(SalesforceModelBase, cls).__new__(cls, name, bases, attrs, **kwargs)
        if models.Model not in bases and supplied_db_table is None:
            result._meta.db_table = result._meta.concrete_model._meta.object_name
            result._meta.original_attrs['db_table'] = result._meta.db_table
        return result

    def add_to_class(cls, name, value):
        # pylint:disable=protected-access
        if name == '_meta':
            sf_custom = False
            if hasattr(value.meta, 'custom'):
                sf_custom = value.meta.custom
                delattr(value.meta, 'custom')
            super(SalesforceModelBase, cls).add_to_class(name, value)  # pylint: disable=no-value-for-parameter
            setattr(cls._meta, 'sf_custom', sf_custom)
        else:
            if type(value) is models.manager.Manager:  # pylint:disable=unidiomatic-typecheck
                # this is for better migrations because: obj._constructor_args = (args, kwargs)
                _constructor_args = value._constructor_args
                value = manager.SalesforceManager()
                value._constructor_args = _constructor_args

            super(SalesforceModelBase, cls).add_to_class(name, value)  # pylint: disable=no-value-for-parameter


# pylint:disable=too-few-public-methods
class SalesforceModel(with_metaclass(SalesforceModelBase, models.Model)):
    """
    Abstract model class for Salesforce objects.
    """
    # pylint:disable=invalid-name
    _salesforce_object = 'standard'
    objects = manager.SalesforceManager()

    class Meta:
        abstract = True
        base_manager_name = 'objects'
        if not DJANGO_20_PLUS:
            manager_inheritance_from_future = True

    # Name of primary key 'Id' can be easily changed to 'id'
    # by "settings.SF_PK='id'".
    id = SalesforceAutoField(primary_key=True, name=SF_PK, db_column='Id',
                             verbose_name='ID', auto_created=True)


class ModelTemplate(object):
    Meta = SalesforceModel.Meta


def make_dynamic_fields(pattern_module, dynamic_field_patterns, attrs):
    """Add some Salesforce fields from a pattern_module models.py

    Parameters:
        pattern_module:  Module where to search additional fields settings.
           It is an imported module created by introspection (inspectdb),
           usually named `models_template.py`. (You will probably not add it
           to version control for you because the diffs are frequent and huge.)
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
    # pylint:disable=invalid-name,too-many-branches,too-many-locals
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
            attname, column = field.get_attname_column()  # pylint:disable=unused-variable
            used_columns.append(column)

    if not pattern_module:
        raise RuntimeError("a pattern_module is required for dynamic fields.")
    for name, obj in vars(pattern_module).items():
        if not name.startswith('_') and isclass(obj) and issubclass(obj, ModelTemplate):
            default_table = obj.__name__
            if getattr(getattr(obj, 'Meta', None), 'db_table', default_table) == db_table:
                cls = obj
                break
    else:
        # not found db_table model, but decide between warning or exception
        if any(not x.startswith('__') for x in dir(pattern_module)):
            raise RuntimeError("No Model for table '%s' found in the module '%s'"
                               % (db_table, pattern_module.__name__))
        warnings.warn("The module '%s' is empty. (It is OK if you are "
                      "rewriting new Models by pipe from inspectdb command.)"
                      % pattern_module.__name__)
        return
    lazy_fields = [(name, obj) for name, obj in vars(cls).items()
                   if isinstance(obj, LazyField) and issubclass(obj.klass, SfField)
                   ]
    for name, obj in sorted(lazy_fields, key=lambda name_obj: name_obj[1].counter):
        for enabled, pat in patterns:
            if pat.match(name):
                break
        else:
            enabled = False
        if enabled:
            if issubclass(obj.klass, ForeignKey):
                to = obj.kw['to']
                if isclass(to) and issubclass(to, ModelTemplate):
                    obj.kw['to'] = to.__name__
            field = obj.create()
            attrs[name] = field
    assert pattern_module  # maybe rarely locked while running inspectdb


Model = SalesforceModel
