from django.core.exceptions import ValidationError
from django.db import models
from .phone_number import PhoneNumber
from .forms import PhoneFormField


class PhoneField(models.CharField):
    empty_values = models.CharField.empty_values + [PhoneNumber('')]

    def __init__(self, *args, **kwargs):
        if kwargs.pop('E164_only', False):
            self.default_validators = [self._validate_E164]
        opts = {
            'max_length': 31
        }
        opts.update(kwargs)
        super(PhoneField, self).__init__(*args, **opts)

    def from_db_value(self, value, expression, connection):
        # Called whenever data is loaded from the DB (the reverse of get_prep_value()).
        # https://docs.djangoproject.com/en/1.10/ref/models/fields/#django.db.models.Field.from_db_value
        return self.to_python(value)

    def to_python(self, value):
        # Called during deserialization and from clean() methods in forms
        if not value:
            return None
        elif isinstance(value, PhoneNumber):
            return value
        return PhoneNumber(value)

    def get_prep_value(self, value):
        if not value:
            return ''

        if not isinstance(value, PhoneNumber):
            value = PhoneNumber(value)
        return value.cleaned

    def formfield(self, **kwargs):
        if kwargs.get('form_class') is None:
            kwargs['form_class'] = PhoneFormField
            kwargs.pop('widget', None)
        return super(PhoneField, self).formfield(**kwargs)

    @staticmethod
    def _validate_E164(value):
        if value and not value.is_E164:
            raise ValidationError('Only E164 numbers are supported here (+12223334444).')
