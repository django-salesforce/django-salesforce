from django.core import exceptions
from django.utils.translation import ugettext_lazy as _
from django.db.models import fields
from django.utils.encoding import smart_unicode

class SalesforceIdField(fields.Field):
	description = _("Text")
	
	empty_strings_allowed = True
	default_error_messages = {
		'invalid': _(u'This value must be a valid Salesforce ID.'),
	}
	def __init__(self, *args, **kwargs):
		assert kwargs.get('primary_key', False) is True, "%ss must have primary_key=True." % self.__class__.__name__
		kwargs['blank'] = True
		kwargs['null'] = True
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
		super(SalesforceIdField, self).contribute_to_class(cls, name)
		cls._meta.has_auto_field = True
		cls._meta.auto_field = self
	
	def formfield(self, **kwargs):
		return None
