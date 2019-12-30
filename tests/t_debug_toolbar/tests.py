"""Test with django-debug-toolbar."""
import datetime
from django.test import TestCase, override_settings
import django.contrib.auth
from salesforce.backend.test_helpers import uid_version as uid, expectedFailure
from salesforce.testrunner.example.models import Campaign, Contact, Lead, Opportunity


@override_settings(DEBUG=True)
class DebugToolbarViewTest(TestCase):
    """Create and delete objects in Salesforce by a simple view."""
    databases = '__all__'

    def test_account_insert_delete(self):
        resp = self.client.get('/account_insert_delete/')
        self.assertContains(resp, 'OK')


@override_settings(DEBUG=True)
class DebugToolbarAdminTest(TestCase):
    """Create objects in Salesforce by Django admin when django-debug-toolbar is enabled."""
    databases = '__all__'

    def setUp(self):
        # Log in as a superuser
        user = django.contrib.auth.models.User.objects.create_user('admin', is_superuser=True, is_staff=True)
        self.client.force_login(user)

    def test_used_debug_toolbar(self):
        """Check that django-debug-toolbar is enabled."""
        resp = self.client.get('/admin/example/campaign/add/')
        self.assertContains(resp, 'djDebugToolbar')

    def test_simple_create(self):
        resp = self.client.post('/admin/example/campaign/add/', {'name': 'test_' + uid})
        self.assertEqual(resp.status_code, 302, "Object not created")
        count_deleted, _ = Campaign.objects.filter(name='test_' + uid).delete()
        self.assertEqual(count_deleted, 1)

    def test_defaulted_numeric_create(self):
        """A simple object with a simple DefaultedOnCreate can be easily filled by web client and saved"""
        # it works becase
        resp = self.client.post(
            '/admin/example/opportunity/add/',
            dict(name='test_' + uid, stage='Prospecting', close_date=datetime.date.today())
        )
        self.assertEqual(resp.status_code, 302, "Object not created")
        opportunities = Opportunity.objects.filter(name='test_' + uid)

        # # this must fail because the DefaultedOnCreate can not pass through a web form
        # self.assertGreater(opportunities[0].probability, 0)

        count_deleted, _ = opportunities.delete()
        self.assertEqual(count_deleted, 1)

    @expectedFailure
    # This fails currently: not enough valid data for this web form because Lead object
    # has many reguired fields. This Lead object is not a good example for web tests.
    # However i works if all required fields are filled manually.
    def test_defaulted_bool_create(self):
        resp = self.client.post('/admin/example/lead/add/', dict(Company='test_' + uid, LastName='some lastname'))
        self.assertEqual(resp.status_code, 302, "Object not created")
        count_deleted, _ = Lead.objects.filter(Company='test_' + uid).delete()
        self.assertEqual(count_deleted, 1)

    @expectedFailure
    # A form with ForeignKey with DefaultedOnCreate fails, because the web widget requires
    # o concrete foreign key value and the object will be not saved.
    def test_defaulted_foreignkey_create(self):
        resp = self.client.post('/admin/example/contact/add/', dict(last_name='test_' + uid))
        self.assertEqual(resp.status_code, 302, "Object not created")
        count_deleted, _ = Contact.objects.filter(Company='test_' + uid).delete()
        self.assertEqual(count_deleted, 1)
