"""Tests by parsing the file modules.py exported by inspectdb

test of a dependent module.
"""
from collections import OrderedDict
from typing import Dict
import os
import re
import unittest


def relative_path(path: str) -> str:
    """
    Return the given path relative to this file.
    """
    return os.path.join(os.path.dirname(__file__), path)


def get_classes_texts() -> Dict[str, str]:
    """
    Get classes texts as a dict.
    """
    result = OrderedDict()
    excluded_pattern = re.compile(r'^('
                                  r'# coding: utf-8|'
                                  r'# This is an auto-generated Django model|'
                                  r'from salesforce import models$'
                                  r')')
    with open(relative_path('models.py'), 'r', newline=None) as f:
        for text in f.read().split('\n\n'):
            text = text.strip()
            if text and not excluded_pattern.match(text):
                match = re.match(r'class (\w+)\(', text)
                assert match
                class_name = match.groups()[0]
                result[class_name] = text
    return result


class ExportedModelTest(unittest.TestCase):

    def match_line(self, pattern, text) -> str:
        """requires the pattern and finds the line"""
        self.assertRegex(text, pattern)
        (ret,) = [line for line in text.split('\n') if re.match(pattern, line)]
        return ret

    def test_nice_fields_names(self) -> None:
        """Test the typical nice field name 'last_modified_date'."""
        for text in classes_texts.values():
            if re.search(r' last_modified_date = ', text):
                line = self.match_line(r'    last_modified_date = ', text)
                self.assertNotIn('db_column', line)
            else:
                self.assertNotIn('lastmodifieddate', text)
                self.assertNotIn('LastModifiedDate', text)

    def test_nice_standard_class_name(self):
        self.assertTrue('AccountContactRole' in classes_texts.keys())

    def test_custom_test_class(self) -> None:
        """Test the typical nice class name 'Test'."""
        for name, text in classes_texts.items():
            if re.search(r"        db_table = 'django_Test__c'", text):
                # test the class name
                self.assertEqual(name, 'DjangoTest')
                # test the field name without db_column
                self.assertNotIn('db_column', self.match_line(r'    test_text = ', text))
                # test foreign kea
                line = self.match_line(r'    contact = ', text)
                self.assertIn('custom=True', line)
                self.assertIn('ForeignKey(Contact', line)
                self.assertIn(', models.DO_NOTHING,', line)
        else:
            self.skipTest("The model for the table Test__c not exported.")

    def test_master_detail_relationship(self) -> None:
        """
        Verify that Contact is a master-detail relationship of Account,
        but Opportunity is not.
        """
        line = self.match_line('    account = ', classes_texts['Contact'])
        self.assertRegex(line, r'#.* Master Detail Relationship \*')
        line = self.match_line('    created_by = ', classes_texts['Opportunity'])
        self.assertNotIn('Master Detail Relationship', line)


classes_texts = get_classes_texts()

if __name__ == '__main__':
    unittest.main()
