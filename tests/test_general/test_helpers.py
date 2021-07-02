# The tests of "dbapi/test_helpers.py" are here, because
# - they should not depend on Django
# - it is not nice to see '(expected failures=1)' in the main test results
#   if we really test the @expectedFailureIf decorator

from unittest import TestCase

from salesforce.dbapi import driver
from salesforce.dbapi.common import get_thread_connections
from salesforce.dbapi.test_helpers import LazyTestMixin, expectedFailureIf

# simulate that a connection exists. It is necessary for `lazy_check()`.
get_thread_connections()['dummy'] = 'dummy'


class TestExpectedFailure(TestCase):

    @expectedFailureIf(False)
    def test_condition_false(self):
        assert True

    @expectedFailureIf(True)
    def test_condition_true(self):
        assert False


class TestLazyAssert(LazyTestMixin, TestCase):

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
        with self.assertRaises(self.LazyAssertionError):
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


class TestLazyAssertNoSetup(LazyTestMixin, TestCase):
    """Verify that LazyTestMixin works also if omitted super().setUp()"""

    def setUp(self):
        # verify that super().setUp() is not necessary for LazyTestMixin
        pass

    def test_fail(self):
        self.lazyAssertTrue(False)
        with self.assertRaises(self.failureException):
            self.lazy_check()

    def test_ok(self):
        self.lazyAssertTrue(True)
        self.lazy_check()


class LazyAssertRequests(LazyTestMixin, TestCase):

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
        """example that a more important error can be caught later
        or than an assert in a lazy test"""
        with self.lazy_assert_n_requests(1):
            driver.request_count += 2  # then check requests
        with self.assertRaises(ZeroDivisionError):
            1 / 0
        with self.assertRaises(self.LazyAssertionError) as cm:
            self.lazy_check()
        exc_class, exc_value, exc_traceback_str = cm.test_case.lazy_failure
        self.assertTrue(issubclass(exc_class, AssertionError))
        self.assertEqual(
            ''.join(exc_value.args),
            '1 != 2 : expected requests != real requests;  checked by:\n    with self.lazy_assert_n_requests(1):'
        )
        self.assertRegex(exc_traceback_str, r'^File ".*", line ')
