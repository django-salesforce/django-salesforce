import logging

from django.conf import settings
from django.db import models

import django_roa

log = logging.getLogger(__name__)

class SalesforceModel(django_roa.Model):
	@staticmethod
	def get_resource_url_list():
		result = u'%s%s' % (settings.SF_SERVER, '/services/data/v23.0/query')
		log.warning(result)
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
	name = models.CharField(max_length=100)


