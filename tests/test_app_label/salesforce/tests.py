"""Backward compatible behaviour with primary key 'Id'."""
from django.test import TestCase
from .models import Contact


class AppLabelTest(TestCase):
    databases = '__all__'

    def test(self):
        obj = Contact.objects.all()[0]
        self.assertEqual(obj._meta.app_label, 'test_salesforce')
