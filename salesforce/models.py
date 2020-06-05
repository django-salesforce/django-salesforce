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

from inspect import isclass
from typing import Any, Dict, Generic, Iterable, Type, TYPE_CHECKING, TypeVar  # noqa
import logging
import types
import warnings

from django.db import models
from django.db.models.base import ModelBase
# Only these two `on_delete` options are currently supported
from django.db.models import PROTECT, DO_NOTHING  # NOQA pylint:disable=unused-wildcard-import,wildcard-import
# from django.db.models import CASCADE, PROTECT, SET_NULL, SET, DO_NOTHING

from salesforce.backend import DJANGO_20_PLUS
from salesforce.defaults import DefaultedOnCreate, DEFAULTED_ON_CREATE
from salesforce.fields import SalesforceAutoField, SF_PK, SfField, ForeignKey
from salesforce.fields import NOT_UPDATEABLE, NOT_CREATEABLE, READ_ONLY
from salesforce.fields import *  # NOQA pylint:disable=unused-wildcard-import,wildcard-import
from salesforce.backend.indep import LazyField
if not TYPE_CHECKING:
    # the SalesforceManager and the module salesforce.backend.manager whould be imported
    # at run-time because it breaks the generic mechanism in `django-stubs` v1.5,
    # that assigns Manager[_T] (a Django manager for the model _T).
    from salesforce.backend import manager

__all__ = ('SalesforceModel', 'Model', 'DEFAULTED_ON_CREATE', 'PROTECT', 'DO_NOTHING', 'SF_PK', 'SfField',
           'NOT_UPDATEABLE', 'NOT_CREATEABLE', 'READ_ONLY', 'DefaultedOnCreate')

log = logging.getLogger(__name__)

_T = TypeVar('_T', bound="models.Model", covariant=True)


class SalesforceModelBase(ModelBase):
    """
    This is a sub-metaclass of the normal Django ModelBase.

    This metaclass overrides the default table-guessing behavior of Django
    and replaces it with code that defaults to the model name.
    """
    # pylint: disable=no-value-for-parameter
    def __new__(cls, name, bases, attrs, **kwargs):  # type: ignore [no-untyped-def] # noqa
        attr_meta = attrs.get('Meta', None)
        supplied_db_table = getattr(attr_meta, 'db_table', None)
        if getattr(attr_meta, 'dynamic_field_patterns', None):
            pattern_module, dynamic_field_patterns = getattr(attr_meta, 'dynamic_field_patterns')
            make_dynamic_fields(pattern_module, dynamic_field_patterns, attrs)
            delattr(attr_meta, 'dynamic_field_patterns')
        result = super(SalesforceModelBase, cls     # type: ignore [call-overload] # noqa
                       ).__new__(cls, name, bases, attrs, **kwargs)
        if models.Model not in bases and supplied_db_table is None:
            result._meta.db_table = result._meta.concrete_model._meta.object_name
            result._meta.original_attrs['db_table'] = result._meta.db_table
        return result

    def add_to_class(cls, name: str, value: Any) -> Any:
        # pylint:disable=protected-access
        if name == '_meta':
            sf_custom = False
            sf_tooling_api_model = False
            if hasattr(value.meta, 'custom'):
                sf_custom = value.meta.custom
                delattr(value.meta, 'custom')
            if hasattr(value.meta, 'sf_tooling_api_model'):
                sf_tooling_api_model = value.meta.sf_tooling_api_model
                delattr(value.meta, 'sf_tooling_api_model')
            super(SalesforceModelBase, cls).add_to_class(name, value)  # type: ignore[misc] # noqa
            setattr(cls._meta, 'sf_custom', sf_custom)  # type: ignore[attr-defined] # noqa
            setattr(cls._meta, 'sf_tooling_api_model', sf_tooling_api_model)  # type: ignore[attr-defined] # noqa
        else:
            if type(value) is models.manager.Manager:  # pylint:disable=unidiomatic-typecheck
                # this is for better migrations because: obj._constructor_args = (args, kwargs)
                _constructor_args = value._constructor_args
                value = models.manager.Manager()
                # value = manager.SalesforceManager()
                value._constructor_args = _constructor_args

            super(SalesforceModelBase, cls).add_to_class(name, value)  # type: ignore[misc] # noqa


if TYPE_CHECKING:
    class SalesforceModel(models.Model, Generic[_T], metaclass=SalesforceModelBase):
        _salesforce_object = ...

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            tmp = models.manager.Manager()  # type: models.manager.Manager[_T]
            self.objects = tmp

        class Meta:
            ...
else:
    # pylint:disable=too-few-public-methods
    class SalesforceModel(models.Model, metaclass=SalesforceModelBase):
        """
        Abstract model class for Salesforce objects.
        """
        # pylint:disable=invalid-name
        _salesforce_object = 'standard'

        # If both managers are specified in this class, they should be different objects,
        # otherwse the name of the base manager must be passed to the mataclass before
        # the name of default manager, but that order is randomized by Python <= 3.5.x
        base_manager = manager.SalesforceManager()  # type: manager.SalesforceManager[_T]
        objects = manager.SalesforceManager()  # type: manager.SalesforceManager[_T]

        class Meta:
            abstract = True
            base_manager_name = 'base_manager'
            if not DJANGO_20_PLUS:
                manager_inheritance_from_future = True

        # Name of primary key 'Id' can be easily changed to 'id'
        # by "settings.SF_PK='id'".
        id = SalesforceAutoField(primary_key=True, name=SF_PK, db_column='Id',
                                 verbose_name='ID', auto_created=True)


class ModelTemplate(object):
    Meta = SalesforceModel.Meta


def make_dynamic_fields(pattern_module: types.ModuleType, dynamic_field_patterns: Iterable[str],
                        attrs: Dict[str, Any]) -> None:
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
        for enabled, pattern in patterns:
            if pattern.match(name):
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
