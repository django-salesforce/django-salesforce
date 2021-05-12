"""Doctests that can be selected by 'manage.py test thismodule.doctests'"""
import doctest

doc_tests = [
    doctest.DocTestSuite('salesforce.backend.introspection'),
]


def load_tests(loader, tests, ignore):
    """Add doctests to unittests"""
    # pylint:disable=unused-argument
    tests.addTests(doc_tests)
    return tests
