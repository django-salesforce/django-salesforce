def doc_tests():
    """Doctests that can be selected by 'manage.py test thismodule.doctests'"""
    import doctest
    return doctest.DocTestSuite('salesforce.backend.introspection')


def load_tests(loader, tests, ignore):
    """Add doctests to unittests"""
    tests.addTests(doc_tests())
    return tests
