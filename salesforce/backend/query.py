import copy

from django.core import serializers
from django.db.models import query as django_query
from django.utils.encoding import force_unicode

import restkit

from django_roa.db import query, exceptions

from salesforce import sfauth

class SalesforceQuerySet(django_query.QuerySet):
	def iterator(self):
		"""
		An iterator over the results from applying this QuerySet to the
		remote web service.
		"""
		import pdb; pdb.set_trace()
		headers = copy.copy(query.ROA_HEADERS)
		
		oauth = sfauth.authenticate()
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

serializers.register_serializer('salesforce', 'salesforce.rest')
