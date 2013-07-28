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


class SfCharField(SfField, models.CharField):
	"""CharField with read_only attribute for Salesforce."""
	pass
class SfEmailField(SfField, models.EmailField):
	"""EmailField with read_only attribute for Salesforce."""
	pass
class SfURLField(SfField, models.URLField):
	"""URLField with read_only attribute for Salesforce."""
	pass
class SfTextField(SfField, models.TextField):
	"""TextField with read_only attribute for Salesforce."""
	pass


class SfIntegerField(SfField, models.IntegerField):
	"""IntegerField with read_only attribute for Salesforce."""
	pass
class SfSmallIntegerField(SfField, models.SmallIntegerField):
	"""SmallIntegerField with read_only attribute for Salesforce."""
	pass
class SfBooleanField(SfField, models.BooleanField):
	"""BooleanField with read_only attribute for Salesforce."""
	pass
class SfDecimalField(SfField, models.DecimalField):
	"""DecimalField with read_only attribute for Salesforce."""
	pass


class SfDateTimeField(SfField, models.DateTimeField):
	"""DateTimeField with read_only attribute for Salesforce."""
	pass
class SfDateField(SfField, models.DateField):
	"""DateField with read_only attribute for Salesforce."""
	pass
class SfTimeField(SfField, models.TimeField):
	"""TimeField with read_only attribute for Salesforce."""
	pass

