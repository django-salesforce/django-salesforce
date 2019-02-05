import unittest
from salesforce.backend.indep import LazyField


class MyField(object):
    # pylint:disable=invalid-name,too-few-public-methods

    def __init__(self, a=None, **kwargs):
        self.kwargs = kwargs
        self.a = a

    @property
    def kw(self):
        kw = self.kwargs
        kw['a'] = self.a
        return kw


class TestLazyField(unittest.TestCase):

    def test_positional_arg(self):
        MyLazyField = LazyField(MyField)
        field = MyLazyField(1)
        self.assertEqual(field.kw, {'a': 1})
        self.assertEqual(field.create().kw, {'a': 1})

    def test_noarg_and_update_later(self):
        MyLazyField = LazyField(MyField)
        self.assertEqual(MyLazyField.klass, MyField)
        field = MyLazyField()
        self.assertTrue(not hasattr(field, 'kwargs'))
        self.assertEqual(field.kw, {'a': None})
        self.assertEqual(field.create().kw, {'a': None})
        field.update(a=7)
        self.assertEqual(field.kw, {'a': 7})
        self.assertEqual(field.create().kw, {'a': 7})

    def test_positional_arg_as_kw(self):
        MyLazyField = LazyField(MyField)
        self.assertEqual(MyLazyField.klass, MyField)
        field = MyLazyField(a=2)
        self.assertEqual(field.kw, {'a': 2})
        self.assertEqual(field.create().kw, {'a': 2})

    def test_kw_args(self):
        MyLazyField = LazyField(MyField)
        field = MyLazyField(b=2, c=3)
        self.assertEqual(field.kw, {'a': None, 'b': 2, 'c': 3})
        self.assertEqual(field.create().kw, {'a': None, 'b': 2, 'c': 3})

    def test_mixed_args(self):
        MyLazyField = LazyField(MyField)
        field = MyLazyField(1, b=4)
        self.assertEqual(field.kw, {'a': 1, 'b': 4})
        self.assertEqual(field.create().kw, {'a': 1, 'b': 4})

    def test_mismatch_args(self):
        MyLazyField = LazyField(MyField)
        with self.assertRaises(TypeError):
            MyLazyField(1, a=1)

    def test_counter(self):
        MyLazyField = LazyField(MyField)
        counter_0 = LazyField.counter
        field_1 = MyLazyField()
        self.assertEqual(field_1.counter, counter_0)
        field_2 = MyLazyField()
        self.assertEqual(field_1.counter, counter_0)
        self.assertEqual(field_2.counter, counter_0 + 1)
        self.assertEqual(LazyField.counter, counter_0 + 2)

    def test_separated(self):
        MyLazyField = LazyField(MyField)
        field_1 = MyLazyField(a=1)
        field_2 = MyLazyField(a=2)
        self.assertEqual((field_1.create().a, field_2.create().a), (1, 2))
