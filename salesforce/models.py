# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

import logging, urllib

from django.conf import settings
from django.db import models
from django.db.models.sql import compiler

from salesforce.backend import base

from salesforce.backend import manager

log = logging.getLogger(__name__)

class SalesforceModel(models.Model):
	objects = manager.SalesforceManager()
	
	class Meta:
		abstract = True
		managed = False
	
	Id = models.CharField(primary_key=True, max_length=100)

class Account(SalesforceModel):
	Name = models.CharField(max_length=100)
	PersonEmail = models.CharField(max_length=100)
	
	def __unicode__(self):
		return self.Name
