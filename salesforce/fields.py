# django-salesforce
#
# by Phil Christensen
# (c) 2012-2013 Freelancers Union (http://www.freelancersunion.org)
# See LICENSE.md for details
#

"""
Adds support for Salesforce primary keys.
"""

from django.core import exceptions
from django.utils.translation import ugettext_lazy as _
from django.db.models import fields
from django.db import models
from django.db.models import ForeignKey
from django.utils.encoding import smart_unicode
try:
	## in south >= 0.6, we have to explicitly tell south about this
	## custom field.  Even though it will be on an unmanaged model, 
	## south parses everything first and will crap out even though
	## later it'd ignore this model anyway.
	from south.modelsinspector import add_introspection_rules
	add_introspection_rules([], ["^salesforce\.fields\.SalesforceAutoField"])
except ImportError:
	pass

class SalesforceAutoField(fields.Field):
	"""
	An AutoField that works with Salesforce primary keys.
	"""
	description = _("Text")
	
	empty_strings_allowed = True
	default_error_messages = {
		'invalid': _(u'This value must be a valid Salesforce ID.'),
	}
	def __init__(self, *args, **kwargs):
		assert kwargs.get('primary_key', False) is True, "%ss must have primary_key=True." % self.__class__.__name__
		kwargs['blank'] = False
		kwargs['null'] = False
		kwargs['default'] = None
		#kwargs.pop('sf_read_only', None)  # TODO currently unused
		fields.Field.__init__(self, *args, **kwargs)
	
	def get_internal_type(self):
		return "AutoField"
	
	def to_python(self, value):
		if isinstance(value, basestring) or value is None:
			return value
		return smart_unicode(value)
	
	def validate(self, value, model_instance):
		pass
	
	def get_prep_value(self, value):
		return self.to_python(value)
	
	def contribute_to_class(self, cls, name):
		assert not cls._meta.has_auto_field, "A model can't have more than one AutoField."
		super(SalesforceAutoField, self).contribute_to_class(cls, name)
		cls._meta.has_auto_field = True
		cls._meta.auto_field = self
	
	def formfield(self, **kwargs):
		return None

class SfField(models.Field):
	"""Add support of sf_read_only attribute for Salesforce fields."""
	def __init__(self, *args, **kwargs):
		sf_read_only = kwargs.pop('sf_read_only', False)
		if sf_read_only:
			kwargs['editable'] = False
		super(SfField, self).__init__(*args, **kwargs)
		self.sf_read_only = sf_read_only


class CharField(SfField, models.CharField):
	"""CharField with sf_read_only attribute for Salesforce."""
	pass
class EmailField(SfField, models.EmailField):
	"""EmailField with sf_read_only attribute for Salesforce."""
	pass
class URLField(SfField, models.URLField):
	"""URLField with sf_read_only attribute for Salesforce."""
	pass
class TextField(SfField, models.TextField):
	"""TextField with sf_read_only attribute for Salesforce."""
	pass


class IntegerField(SfField, models.IntegerField):
	"""IntegerField with sf_read_only attribute for Salesforce."""
	pass
class SmallIntegerField(SfField, models.SmallIntegerField):
	"""SmallIntegerField with sf_read_only attribute for Salesforce."""
	pass
class BooleanField(SfField, models.BooleanField):
	"""BooleanField with sf_read_only attribute for Salesforce."""
	pass
class DecimalField(SfField, models.DecimalField):
	"""DecimalField with sf_read_only attribute for Salesforce."""
	pass


class DateTimeField(SfField, models.DateTimeField):
	"""DateTimeField with sf_read_only attribute for Salesforce."""
	pass
class DateField(SfField, models.DateField):
	"""DateField with sf_read_only attribute for Salesforce."""
	pass
class TimeField(SfField, models.TimeField):
	"""TimeField with sf_read_only attribute for Salesforce."""
	pass

AutoField = SalesforceAutoField
