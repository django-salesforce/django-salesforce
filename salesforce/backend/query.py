import copy

from django.core import serializers
from django.db.models import query as django_query
from django.utils.encoding import force_unicode

import restkit

import django_roa
from django_roa.db import query, managers, exceptions

class SalesforceQuerySet(django_query.QuerySet):
	def iterator(self):
		"""
		An iterator over the results from applying this QuerySet to the
		remote web service.
		"""
		headers = copy.copy(query.ROA_HEADERS)
		oauth = authenticate()
		headers['Authorization'] = 'OAuth %s' % oauth['access_token']
		resource = restkit.Resource(self.model.get_resource_url_list(self, server=oauth['instance_url']))
		
		try:
			response = resource.get(headers=headers)
		except restkit.ResourceNotFound:
			return
		except Exception, e:
			raise exceptions.ROAException(e)
		
		body = response.body_string()
		response = force_unicode(body).encode(settings.DEFAULT_CHARSET)
		for local_name, remote_name in query.ROA_MODEL_NAME_MAPPING:
			response = response.replace(remote_name, local_name)
		
		ROA_FORMAT = getattr(settings, "ROA_FORMAT", 'json')
		for res in serializers.deserialize(ROA_FORMAT, response):
			obj = res.object
			yield obj

class SalesforceManager(managers.ROAManager):
	def get_query_set(self):
		"""
		Returns a QuerySet which access remote resources.
		"""
		return SalesforceQuerySet(self.model)

serializers.register_serializer('salesforce', 'salesforce.rest')
