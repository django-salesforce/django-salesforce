import re
import sys
from django.test import TestCase
import django
from salesforce import backend


class VersionTest(TestCase):
    def test_version(self):
        """Check that the expected Django version is being tested

        "tox" sometimes installed an incorrect Django version,
        e.g. if versions required by tox deps or setup.py are in conflict.
        The unexpected version should be immediately uninstalled and replaced by a requiered version.
        """
        match = re.search(r'/\.tox/dj(\d+|dev)-py(\d+)/', django.__file__)
        if match:
            django_version_abbr, python_version_abbr = match.groups()
            if django_version_abbr == 'dev':
                self.assertTrue(backend.is_dev_version, "This should be a test environment of a DEV version")
                self.assertGreater(django.VERSION[:2], backend.max_django)
            else:
                self.assertEqual('{}{}'.format(*django.VERSION[:2]), django_version_abbr)
            self.assertEqual('{}{}'.format(*sys.version_info[:2]), python_version_abbr)
