from django.test import TestCase
import django.contrib.auth


class WebTest(TestCase):
	def test_admin(self):
		"""Test that mainly improves code coverage."""

		# Log in as a superuser
		user = django.contrib.auth.models.User.objects.create_user('fredsu', 'fred@example.com', 'passwd')
		user.is_superuser = True
		user.is_staff = True
		user.save()
		self.client.login(username='fredsu', password='passwd')

		response = self.client.get('/')
		response = self.client.get('/search/')
		response = self.client.get('/search/')
		response = self.client.post('/admin/example/account/')
		response = self.client.post('/admin/example/contact/')
		response = self.client.post('/admin/example/lead/')
		response = self.client.post('/admin/example/pricebook/')
		response = self.client.post('/admin/')
		self.assertIn('PricebookEntries', response.rendered_content)
