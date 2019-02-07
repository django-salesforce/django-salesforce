"""Backward compatible behaviour with primary key 'Id'."""
from __future__ import absolute_import
from django.test import TestCase
from .models import Contact


class AppLabelTest(TestCase):
    databases = '__all__'

    def test(self):
        obj = Contact.objects.all()[0]
        self.assertEqual(obj._meta.app_label, 'test_salesforce')
