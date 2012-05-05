# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
#

import logging, urllib

from django.conf import settings
from django.db import models
from django.db.models.sql import compiler

from fu_web.salesforce.backends.salesforce import base

import django_roa

log = logging.getLogger(__name__)

class SalesforceModel(django_roa.Model):
	class Meta:
		abstract = True
	
	Id = models.CharField(primary_key=True, max_length=100)
	
	@staticmethod
	def get_resource_url_list(queryset, server=settings.SF_SERVER):
		conn = base.DatabaseWrapper()
		sql, params = base.SQLCompiler(queryset.query, conn, None).as_sql()
		rendered_query = sql % params
		result = u'%s%s?%s' % (server, '/services/data/v23.0/query', urllib.urlencode(dict(
			q	= rendered_query,
		)))
		log.info(rendered_query)
		return result
	
	def get_resource_url_count(self):
		log.error('count')
		import pdb; pdb.set_trace()
		return u"%scount/" % (self.get_resource_url_list(),)
	
	def get_resource_url_detail(self):
		log.error('detail')
		import pdb; pdb.set_trace()
		return u"%s%s/" % (self.get_resource_url_list(), self.pk)

class Account(SalesforceModel):
	Name = models.CharField(max_length=100)
	
	def __unicode__(self):
		return self.Name
