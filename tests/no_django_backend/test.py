import unittest
import salesforce.backend
import salesforce.testrunner.settings

sf_alias = 'salesforce'
settings_dict = salesforce.testrunner.settings.DATABASES[sf_alias]


class Test(unittest.TestCase):

    def test_no_django(self):
        self.assertRaises(ImportError, __import__, 'django.core')
