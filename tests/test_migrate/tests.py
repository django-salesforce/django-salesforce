"""A writable test, not specifically important what is tested"""
from django.test import TestCase

from .models import Contact


class CompatibilityTest(TestCase):
    databases = '__all__'

    def test_capitalized_id(self):
        test_contact = Contact(last_name='Smith')
        test_contact.save()
        try:
            refreshed_contact = Contact.objects.get(pk=test_contact.pk)
            self.assertEqual(refreshed_contact.pk, test_contact.pk)
        finally:
            test_contact.delete()
