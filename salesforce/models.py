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

import logging

from django.conf import settings
from django.db import models
from django.db.models.base import ModelBase
from django.db.models.sql import compiler
# Only these two `on_delete` options are currently supported
from django.db.models import PROTECT, DO_NOTHING
#from django.db.models import CASCADE, PROTECT, SET_NULL, SET, DO_NOTHING
from django.utils.six import with_metaclass

from salesforce.backend import manager
from salesforce.fields import *  # modified django.db.models.CharField etc.
from salesforce import fields, DJANGO_15

log = logging.getLogger(__name__)

class SalesforceModelBase(ModelBase):
	"""
	This is a sub-metaclass of the normal Django ModelBase.
	
	This metaclass overrides the default table-guessing behavior of Django
	and replaces it with code that defaults to the model name.
	"""
	def __new__(cls, name, bases, attrs):
		supplied_db_table = getattr(attrs.get('Meta', None), 'db_table', None)
		result = super(SalesforceModelBase, cls).__new__(cls, name, bases, attrs)
		if(models.Model not in bases and supplied_db_table is None):
			result._meta.db_table = name
		return result


if DJANGO_15:

	class SalesforceModel(with_metaclass(SalesforceModelBase, models.Model)):
		"""
		Abstract model class for Salesforce objects.
		"""
		_base_manager = objects = manager.SalesforceManager()
		_salesforce_object = True
		
		class Meta:
			managed = False
			abstract = True
		
		Id = fields.SalesforceAutoField(primary_key=True)

else:  # old Django 1.4 uncompatible with Python 3

	class SalesforceModel(models.Model):
		"""
		Abstract model class for Salesforce objects.
		"""
		__metaclass__ = SalesforceModelBase
		_base_manager = objects = manager.SalesforceManager()
		_salesforce_object = True
		
		class Meta:
			managed = False
			abstract = True
		
		Id = fields.SalesforceAutoField(primary_key=True)

Model = SalesforceModel
