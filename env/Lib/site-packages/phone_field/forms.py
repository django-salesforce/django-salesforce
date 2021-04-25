from django import forms
from .phone_number import PhoneNumber, BACKEND_EXTENSION_SEPARATOR


class PhoneWidget(forms.MultiWidget):
    template_name = r'phone_field/phone_widget.html'

    def __init__(self, attrs={}, phone_attrs=None, ext_attrs=None):   
        def_phone_attrs = {'size': 13}
        def_phone_attrs.update(phone_attrs or attrs)
        def_ext_attrs = {'size': 4}
        def_ext_attrs.update(ext_attrs or attrs)
        widgets = (
            forms.TextInput(def_phone_attrs),
            forms.TextInput(def_ext_attrs)
        )
        super().__init__(widgets, attrs=attrs)

    def decompress(self, value):
        if not isinstance(value, PhoneNumber):
            value = PhoneNumber(value)
        return value.base_number_fmt, BACKEND_EXTENSION_SEPARATOR.join(value.extensions)

    def get_context(self, name, value, attrs):
        # First sub-widget doesn't get marked as required for some reason
        self.widgets[0].is_required = attrs.get('required', False)
        ctx = super().get_context(name, value, attrs)

        # `get_context()` blindly copies the "required" HTML attribute from PhoneFormField to all of the sub-widget
        # attrs. This is the opposite of the above problem, where "required" doesn't get set in the context.
        # The text input for phone extension should always be optional. Not sure why Django isn't taking care of this.
        ctx['widget']['subwidgets'][1]['attrs']['required'] = False
        return ctx


class PhoneFormField(forms.MultiValueField):
    widget = PhoneWidget

    def __init__(self, *, require_all_fields=False, **kwargs):
        self.max_length = kwargs.pop('max_length', None)

        # Disregard 'empty_value' kwarg from CharField model defaults
        kwargs.pop('empty_value', None)

        fields = (
            forms.CharField(),
            forms.CharField(required=False)
        )
        super().__init__(fields, require_all_fields=require_all_fields, **kwargs)

    def compress(self, data_list):
        # A completely empty widget short-circuits normal validation and returns []
        if not data_list:
            return PhoneNumber('')

        str_val = BACKEND_EXTENSION_SEPARATOR.join(x for x in data_list if x)
        return PhoneNumber(str_val)

    def validate(self, value):
        if self.max_length is not None and value and len(value) > self.max_length:
            raise forms.ValidationError('Phone number is too long.')
