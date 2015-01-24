"""Tests by parsing the file modules.py exported by inspectdb."""
import unittest
import os
import re

try:
	from collections import OrderedDict
except ImportError:
	from django.utils.datastructures import SortedDict as OrderedDict


def relative_path(path):
	"""
	Return the given path relative to this file.
	"""
	return os.path.join(os.path.dirname(__file__), path)


def get_classes_texts():
	"""
	Get classes texts as a dict.
	"""
	result = OrderedDict()
	excluded_pattern = re.compile(r'^('
			r'# coding: utf-8|'
			r'# This is an auto-generated Django model|'
			r'from salesforce import models$'
		')')
	with open(relative_path('models.py'), 'rU') as f:
		for text in f.read().split('\n\n'):
			text = text.strip()
			if text and not excluded_pattern.match(text):
				class_name = re.match(r'class (\w+)\(', text).groups()[0]
				result[class_name] = text
	return result


class ExportedModelTest(unittest.TestCase):
	def test_nice_fields_names(self):
		"""Test the typical nice field name 'last_modified_date'."""
		for text in classes_texts.values():
			if re.search(r' last_modified_date = ', text):
				(matched_line,) = [line for line in text.split('\n')
						if re.match(r'    last_modified_date = ', line)]
				self.assertNotIn('db_column', matched_line)
			else:
				self.assertNotIn('lastmodifieddate', text)
				self.assertNotIn('LastModifiedDate', text)

	def test_custom_test_class(self):
		"""Test the typical nice class name 'Test'."""
		self.assertTrue('AccountContactRole' in classes_texts.keys())
		for name, text in classes_texts.items():
			if re.search(r"        db_table = 'Test__c'", text):
				# test the class name
				self.assertEqual(name, 'Test')
				# test the field name without db_column
				(matched_line,) = [line for line in text.split('\n')
						if re.match(r'    test_field = ', line)]
				self.assertNotIn('db_column', matched_line)
				break
		else:
			self.skipTest("The model for the table Test__c not exported.")

classes_texts = get_classes_texts()

if __name__ == '__main__':
	unittest.main()
