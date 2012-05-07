# django-salesforce
#
# by Phil Christensen
# (c) 2012 Working Today
# See LICENSE.md for details
#

from django.core.serializers.python import Serializer as PythonSerializer
from django.core.serializers.python import Deserializer as PythonDeserializer

try:
	from cStringIO import StringIO
except ImportError:
	from StringIO import StringIO

try:
	import json
except ImportError:
	import simplejson as json

class Serializer(PythonSerializer):
	"""
	Convert a queryset to JSON.
	"""
	internal_use_only = False

	def end_serialization(self):
		json.dump(self.objects, self.stream, **self.options)

	def getvalue(self):
		if callable(getattr(self.stream, 'getvalue', None)):
			return self.stream.getvalue()

def Deserializer(stream_or_string, **options):
	"""
	Deserialize a stream or string of JSON data.
	"""
	if isinstance(stream_or_string, basestring):
		stream = StringIO(stream_or_string)
	else:
		stream = stream_or_string
	
	def _mkrecords(data):
		for record in data['records']:
			attribs = record.pop('attributes')
			yield dict(
				model	= 'salesforce.%s' % attribs['type'],
				pk		= record.pop('Id'),
				fields  = record,
			)
	
	data = json.load(stream)
	for obj in PythonDeserializer(_mkrecords(data), **options):
		yield obj
