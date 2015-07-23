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

from django.conf import settings
from django.db import models
from django.db.models.base import ModelBase
from django.db.models.sql import compiler
# Only these two `on_delete` options are currently supported
from django.db.models import PROTECT, DO_NOTHING
#from django.db.models import CASCADE, PROTECT, SET_NULL, SET, DO_NOTHING

from salesforce.backend import manager
from salesforce.fields import *  # modified django.db.models.CharField etc.
from salesforce import fields, DJANGO_17_PLUS
if DJANGO_17_PLUS:
	from django.utils.deconstruct import deconstructible
else:
	deconstructible = lambda x: x

log = logging.getLogger(__name__)


class SalesforceModelBase(ModelBase):
	"""
	This is a sub-metaclass of the normal Django ModelBase.

	This metaclass overrides the default table-guessing behavior of Django
	and replaces it with code that defaults to the model name.
	"""
	def __new__(cls, name, bases, attrs):
		attr_meta = attrs.get('Meta', None)
		supplied_db_table = getattr(attr_meta, 'db_table', None)
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


# Backported for Django 1.4 from django.utils.six version 1.7
def with_metaclass(meta, *bases):
	"""Create a base class with a metaclass."""
	# This requires a bit of explanation: the basic idea is to make a
	# dummy metaclass for one level of class instantiation that replaces
	# itself with the actual metaclass.  Because of internal type checks
	# we also need to make sure that we downgrade the custom metaclass
	# for one level to something closer to type (that's why __call__ and
	# __init__ comes back from type etc.).
	class metaclass(meta):
		__call__ = type.__call__
		__init__ = type.__init__
		def __new__(cls, name, this_bases, d):
			if this_bases is None:
				return type.__new__(cls, name, (), d)
			return meta(name, bases, d)
	return metaclass(str('temporary_class'), None, {})


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
	id = fields.SalesforceAutoField(primary_key=True, name=SF_PK, db_column='Id',
									verbose_name='ID', auto_created=True)


@deconstructible
class DefaultedOnCreate(object):
	"""
	Default value for foreign keys that but will get a smart auto value from
	SFDC on create if the field is omitted, but can not be assigned to null in
	the API.
	(builtin SFDC fields with attributes 'defaultedOnCreate: true, nillable: false')

	Example: `Owner` field is assigned to the current user if the field User is omitted.

		Owner = models.ForeignKey(User, on_delete=models.DO_NOTHING,
				default=models.DefaultedOnCreate(),
				db_column='OwnerId')
	"""
	def __str__(self):
		return 'DEFAULTED_ON_CREATE'


DEFAULTED_ON_CREATE = DefaultedOnCreate()
Model = SalesforceModel
