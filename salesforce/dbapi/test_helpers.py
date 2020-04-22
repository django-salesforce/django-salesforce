import sys
import traceback
import unittest
from contextlib import contextmanager
from unittest import expectedFailure
from unittest import mock  # pylint:disable=unused-import  # NOQA
from typing import Any, Callable, List, Iterator, Optional, Tuple, Type, TYPE_CHECKING

from salesforce.dbapi import connections, driver
TestMethod = Callable[..., None]


def expectedFailureIf(condition: bool) -> Callable[[TestMethod], TestMethod]:
    """Conditional 'expectedFailure' decorator for TestCase"""
    if condition:
        return expectedFailure
    return lambda func: func


class QuietSalesforceErrors(object):
    """Context manager that helps expected SalesforceErrors to be not logged too verbose.

    It works on the default Salesforce connection. It can be nested.
    """
    def __init__(self, alias: Optional[str], verbs: Optional[List[str]] = None):
        self.connection = connections[alias]
        self.verbs = verbs
        self.save_debug_verbs = None

    def __enter__(self) -> 'QuietSalesforceErrors':
        self.save_debug_verbs = self.connection.connection.debug_verbs
        self.connection.connection.debug_verbs = self.verbs
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException], exc_tb: Any
                 ) -> None:
        try:
            self.connection.connection.debug_verbs = self.save_debug_verbs
        except AttributeError:
            pass


if TYPE_CHECKING:
    BaseLazyTestMixin = unittest.TestCase
else:
    BaseLazyTestMixin = object


class LazyTestMixin(BaseLazyTestMixin):
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

    def setUp(self) -> None:  # pylint:disable=invalid-name
        self.lazy_failure = None  # type: Optional[Tuple[Type[BaseException], BaseException, str]]

    def _lazy_assert(self, assert_method: TestMethod, *args: Any, **kwargs: Any) -> None:
        def stack_of_test_method(raw_stack: List[Any]) -> List[str]:
            stack = traceback.format_list(raw_stack)
            parent_frame = max((i for i, x in enumerate(stack) if x.endswith(' testMethod()\n')), default=0)
            if not parent_frame:
                # this is for Python >= 3.8
                parent_frame = 1 + max(
                    (i for i, x in enumerate(stack) if x.endswith('_callTestMethod(testMethod)\n')), default=-1)
            return stack[1 + parent_frame:-skip_frames]

        if not getattr(self, 'lazy_failure', None):
            skip_frames = kwargs.pop('skip_frames', 2)
            # the name is like in unittests due to more readable test tracebacks
            lazyAssertMethod = assert_method  # pylint:disable=invalid-name
            try:
                lazyAssertMethod(*args, **kwargs)
            except self.failureException:
                exc_type, exc_value, _ = sys.exc_info()
                stack = stack_of_test_method(traceback.extract_stack())
                assert exc_type and exc_value
                self.lazy_failure = exc_type, exc_value, ''.join(stack).strip()

    def lazy_check(self) -> None:
        """Check all previous `lazy_assert_*`"""
        lazy_failure = getattr(self, 'lazy_failure', None)
        if lazy_failure:
            exc_type, original_exception, traceback_part_text = lazy_failure
            msg = original_exception.args[0]
            original_exception = self.LazyAssertionError(
                '\n'.join((
                    '\nUse the first frame of this real traceback and ignore the previous lazy traceback:',
                    traceback_part_text,
                    '{}: {}'.format(exc_type.__name__, msg),
                )),
                *original_exception.args[1:]
            )
            raise original_exception

    # pylint:disable=invalid-name
    def lazyAssertTrue(self, expr: Any, msg: Optional[str] = None) -> None:
        self._lazy_assert(self.assertTrue, expr, msg=msg)

    def lazyAssertEqual(self, expr_1: Any, expr_2: Any, msg: Optional[str] = None) -> None:
        self._lazy_assert(self.assertEqual, expr_1, expr_2, msg=msg)

    @contextmanager
    def lazy_assert_n_requests(self, expected_requests: int, msg: Optional[str] = None) -> Iterator[None]:
        """Assert that the inner block requires expected_requests, evaluated lazily."""
        request_count_0 = driver.request_count
        try:
            yield None
        finally:
            request_count_1 = driver.request_count
            msg = (msg + '\n') if msg else ''
            msg += ('expected requests != real requests;  checked by:\n'
                    '    with self.lazy_assert_n_requests({}):'.format(expected_requests))
            self.lazyAssertEqual(expected_requests, request_count_1 - request_count_0, msg=msg)
