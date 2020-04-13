"""Test that app config can override a directory name conflict (.e.g. "salesforce")"""
from salesforce.testrunner.settings import *  # NOQA pylint: disable=unused-wildcard-import,wildcard-import
from salesforce.testrunner.settings import INSTALLED_APPS

INSTALLED_APPS = [x for x in INSTALLED_APPS if x != 'salesforce.testrunner.example']
INSTALLED_APPS += ['tests.test_app_label.salesforce.apps.TestSalesForceConfig']
ROOT_URLCONF = None
