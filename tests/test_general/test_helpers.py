# The tests of "dbapi/test_helpers.py" are here, because
# - they should not depend on Django
# - it is not nice to see '(expected failures=1)' in the main test results
#   if we really test the @expectedFailureIf decorator

from unittest import TestCase

from salesforce.dbapi import driver
from salesforce.dbapi.test_helpers import LazyTestMixin, expectedFailureIf


class TestExpectedFailure(TestCase):

    @expectedFailureIf(False)
    def test_condition_false(self):
        assert True

    @expectedFailureIf(True)
    def test_condition_true(self):
        assert False


class TestLazyAssert(TestCase, LazyTestMixin):

    def test_lazy_assert_fail(self):
        """example of an failed test if any lazy_assert fails"""
        self.lazyAssertTrue(True)
        self.lazyAssertTrue(False)
        self.lazyAssertTrue(True)
        # here would pass some important test
        with self.assertRaises(self.failureException):
            self.lazy_check()

    def test_error(self):
        """example that an error is more important than a failed lazy_assert"""
        self.lazyAssertTrue(False)
        with self.assertRaises(ZeroDivisionError):
            1 / 0
            self.lazy_check()

    def test_ok(self):
        """example that more asserts can be checked together"""
        self.lazyAssertTrue(True)
        self.lazyAssertTrue(True)
        self.lazy_check()

    def test_finally(self):
        """example of a test with a cean up after "finally:"

        The command "lazy_check()" should be before "finally:", because:
          - lazy_check() can raise probably.
          - only the more important exception should be raised if it occurs
        """
        with self.assertRaises(self.failureException):
            try:
                self.lazyAssertTrue(False)
                # other code that can fail
                # ...
                self.lazy_check()
            finally:
                clean_up = True  # some cleanup
        self.assertTrue(clean_up)


class TestLazyAssertNoSetup(TestCase, LazyTestMixin):

    def setUp(self):
        # this overshadowed "setUp" in LazyTestMixin
        # by omitting  super(..., self).setUp()
        pass

    def test_fail(self):
        self.lazyAssertTrue(False)
        with self.assertRaises(self.failureException):
            self.lazy_check()

    def test_ok(self):
        self.lazyAssertTrue(True)
        self.lazy_check()


class LazyAssertRequests(TestCase, LazyTestMixin):

    def test_ok(self):
        """example that more asserts can be checked together"""
        try:
            with self.lazy_assert_n_requests(1):
                driver.request_count += 1
            self.lazy_check()
        finally:
            pass  # some cleanup

    def test_fail(self):
        """example of an failed test of requests"""
        with self.lazy_assert_n_requests(1):
            driver.request_count += 2
        with self.assertRaises(self.failureException):
            self.lazy_check()

    def test_error(self):
        """example that an error is more important than a lazy test"""
        with self.lazy_assert_n_requests(1):
            driver.request_count += 2  # then check requests
        with self.assertRaises(ZeroDivisionError):
            1 / 0
            self.lazy_check()
