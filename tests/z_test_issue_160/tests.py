"""Test djangoBackward compatible behaviour with primary key 'Id'."""
from __future__ import absolute_import
from django.test import TestCase

from .models import Contact


class CompatibilityTest(TestCase):
    def test_capitalized_id(self):
        test_contact = Contact(last_name='Smith')
        test_contact.save()
        try:
            refreshed_contact = Contact.objects.get(id=test_contact.id)
            self.assertEqual(refreshed_contact.id, test_contact.id)
        finally:
            test_contact.delete()
