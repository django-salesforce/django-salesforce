import re
import sys
from django.test import TestCase
import django


class VersionTest(TestCase):
    def test_version(self):
        """Check that the expected Django version is being tested

        "tox" sometimes installed incorrect Django versions installed by "tox",
        e.g. if versions required by tox deps and requirements.txt or setup.py
        are in conflict. The righ version could be immediately uninstalled and
        replaced by an invalid version.
        """
        match = re.search(r'/\.tox/py(\d+)-dj(\d+)/', django.__file__)
        if match:
            python_version_abbr, django_version_abbr = match.groups()
            self.assertEqual('{}{}'.format(*django.VERSION[:2]), django_version_abbr)
            self.assertEqual('{}{}'.format(*sys.version_info[:2]), python_version_abbr)
