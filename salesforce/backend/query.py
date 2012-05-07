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

class CursorWrapper(object):
	def __init__(self, settings_dict):
		self.settings_dict = settings_dict
		connection_created.send(sender=self.__class__, connection=self)
		self.oauth = sfauth.authenticate(self.settings_dict)
	
	def execute(self, query, args=None):
		pass
	
	def executemany(self, query, args=None):
		pass

serializers.register_serializer('salesforce', 'salesforce.rest')
