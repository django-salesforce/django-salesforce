# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

"""
Django models for accessing Salesforce objects.

The Salesforce database is somewhat un-UNIXy or non-Pythonic, in that
column names are all in CamelCase. No attempt is made to work around this
issue, but normal use of `db_column` and `table_name` parameters should work.
"""

import logging, urllib

from django.conf import settings
from django.db import models
from django.db.models.sql import compiler

from salesforce.backend import base, manager
from salesforce import fields

log = logging.getLogger(__name__)

class SalesforceModel(models.Model):
	"""
	Abstract model class for Salesforce objects.
	
	For convenience, this is encapsulated as a superclass, but if you
	need to inherit from another model class for some reason, you'll need
	override the 'objects' manager instance with the SalesforceManager,
	as well as create some kind of solution for routing to the proper
	database connection (salesforce.router.ModelRouter only looks for
	SalesforceModel subclasses).
	"""
	_base_manager = objects = manager.SalesforceManager()
	
	class Meta:
		abstract = True
		managed = False
	
	Id = fields.SalesforceIdField(primary_key=True)

