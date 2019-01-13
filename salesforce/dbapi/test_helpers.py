import sys
import traceback
from contextlib import contextmanager

from salesforce.backend import driver


class LazyTestMixin(object):
    """Report less important asserts lazily, only if no more important failure occurs.

    Only the first lazy_assert(...) failure is reported at the end of test at "lazy_check()"
    and only if no more important failure occurs between lazy_assert and lazy_check.

        self.lazy_assert(expr...)
        ...
        self.assertEqual(expr...)
        ...
        self.lazy_assert(expr...)
        ...
        self.assertEqual(expr...)
        ...
        self.assert_check()
    """
    class LazyAssertionError(AssertionError):
        pass

    def setUp(self):  # pylint:disable=invalid-name
        self.lazy_failure = None

    def _lazy_assert(self, assert_method, *args, **kwargs):
        if not getattr(self, 'lazy_failure', None):
            skip_frames = kwargs.pop('skip_frames', 2)
            # the name is like in unittests due to more readable test tracebacks
            lazyAssertMethod = assert_method  # pylint:disable=invalid-name
            try:
                lazyAssertMethod(*args, **kwargs)
            except self.failureException:
                exc_type, exc_value, _ = sys.exc_info()
                stack = traceback.format_list(traceback.extract_stack())
                stack = stack[1 + max(i for i, x in enumerate(stack) if x.endswith(' testMethod()\n')):-skip_frames]
                self.lazy_failure = exc_type, exc_value, ''.join(stack).strip()

    def lazy_check(self):
        """Check all previous `lazy_assert_*`"""
        if getattr(self, 'lazy_failure', None):
            exc_type, original_exception, traceback_part_text = self.lazy_failure
            msg = original_exception.args[0]
            original_exception = self.LazyAssertionError(
                '\n'.join((
                    '(Use the next traceback, ignore the previous traceback):',
                    traceback_part_text,
                    '{}: {}'.format(exc_type.__name__, msg),
                )),
                *original_exception.args[1:]
            )
            raise original_exception

    # pylint:disable=invalid-name
    def lazyAssertTrue(self, expr, msg=None):
        self._lazy_assert(self.assertTrue, expr, msg=msg)

    def lazyAssertEqual(self, expr_1, expr_2, msg=None):
        self._lazy_assert(self.assertEqual, expr_1, expr_2, msg=msg)

    @contextmanager
    def lazy_assert_n_requests(self, expected_requests, msg=None):
        """Assert that the inner block requires expected_requests, evaluated lazily."""
        request_count_0 = driver.request_count
        try:
            yield None
        finally:
            request_count_1 = driver.request_count
            msg = (msg + '\n') if msg else ''
            msg += ('expected requests != real requests;  checked by:\n'
                    'with self.lazy_assert_n_requests({}):'.format(expected_requests))
            self.lazyAssertEqual(expected_requests, request_count_1 - request_count_0, msg=msg)
