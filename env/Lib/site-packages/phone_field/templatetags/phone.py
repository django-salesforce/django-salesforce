from django import template
from ..phone_number import PhoneNumber


register = template.Library()


@register.filter(name='phone')
def format_phone(phone_number):
    if not phone_number:
        return ''
    elif not isinstance(phone_number, PhoneNumber):
        phone_number = PhoneNumber(phone_number)
    return str(phone_number)


# Raw phone number
@register.filter(name='raw_phone')
def raw_phone(phone_number):
    if not phone_number:
        return phone_number
    elif isinstance(phone_number, PhoneNumber):
        return phone_number.cleaned
    return ''.join(c for c in phone_number if c.isdigit())
