"""
A writable test, not specifically important what is tested

both databases are non-salesforce
"""
from django.conf import settings
from django.test import TestCase

from salesforce.backend.test_helpers import default_is_sf
from .models import Contact, User


class CompatibilityTest(TestCase):
    databases = '__all__'

    def test_capitalized_id(self):
        # prepare a Contact
        test_contact = Contact(last_name='Smith')
        if not default_is_sf:
            # If SALESFORCE_DB_ALIAS is not a Salesforce database then a user must be created
            # and set as the owner, because DefaultedOnCreate works only on SFDC servers
            test_user = User.objects.create(username='test', last_name='test', email='test@example.com')
            test_contact.owner = test_user
        test_contact.save()

        # test that the primary key 'Id' works
        sf_pk = getattr(settings, 'SF_PK', 'id')
        self.assertTrue(hasattr(test_contact, sf_pk))
        try:
            refreshed_contact = Contact.objects.get(pk=test_contact.pk)
            self.assertEqual(refreshed_contact.pk, test_contact.pk)
        finally:
            test_contact.delete()
