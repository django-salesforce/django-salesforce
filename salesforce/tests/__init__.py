from django.utils import unittest

def load_test_suite(package_name):
	suite = unittest.TestSuite()
	loader = unittest.TestLoader()

	for test in loader.discover(package_name):
		suite.addTest(test)

	return lambda: suite

suite = load_test_suite(__name__)