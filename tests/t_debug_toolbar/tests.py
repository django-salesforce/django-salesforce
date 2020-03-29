"""Test with django-debug-toolbar."""
from django.test import TestCase, override_settings
import django.contrib.auth
from salesforce.backend.test_helpers import uid_version as uid
from salesforce.testrunner.example.models import Campaign


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
