from unittest import TestCase
from salesforce.dbapi.subselect import (
    find_closing_parenthesis, split_subquery, transform_except_subquery,
    mark_quoted_strings, subst_quoted_strings, simplify_expression,
)


class TestSubSelectSearch(TestCase):
    def test_parenthesis(self):
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 0), (0, 2))
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 2), (3, 12))
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 3), (3, 12))
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 6), (7, 11))
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 13), (13, 15))
        self.assertRaises(AssertionError, find_closing_parenthesis, '() (() (())) ()', 1)

    def test_subquery(self):
        def func(x):  # pylint:disable=unused-argument
            return '*transformed*'

        sql = "SELECT a, (SELECT x FROM y) FROM b WHERE (c IN (SELECT p FROM q WHERE r = %s) AND c = %s)"
        expected = "*transformed*(SELECT x FROM y)*transformed*(SELECT p FROM q WHERE r = %s)*transformed*"
        self.assertEqual(transform_except_subquery(sql, func), expected)

    def test_split_subquery(self):
        sql = " SELECT a, ( SELECT x FROM y) FROM b WHERE (c IN (SELECT p FROM q WHERE r = %s) AND c = %s)"
        expected = ("SELECT a, (&) FROM b WHERE (c IN (&) AND c=%s)",
                    [("SELECT x FROM y", []),
                     ("SELECT p FROM q WHERE r=%s", [])
                     ])
        self.assertEqual(split_subquery(sql), expected)

    def test_nested_subquery(self):
        def func(x):  # pylint:disable=unused-argument
            return '*transformed*'

        sql = "SELECT a, (SELECT x, (SELECT p FROM q) FROM y) FROM b"
        expected = "*transformed*(SELECT x, (SELECT p FROM q) FROM y)*transformed*"
        self.assertEqual(transform_except_subquery(sql, func), expected)

    def test_split_nested_subquery(self):
        sql = "SELECT a, (SELECT x, (SELECT p FROM q) FROM y) FROM b"
        expected = ("SELECT a, (&) FROM b",
                    [("SELECT x, (&) FROM y",
                      [("SELECT p FROM q", [])]
                      )]
                    )
        self.assertEqual(split_subquery(sql), expected)


class ReplaceQuotedStringsTest(TestCase):
    def test_subst_quoted_strings(self):
        def inner(sql, expected):
            result = mark_quoted_strings(sql)
            self.assertEqual(result, expected)
            self.assertEqual(subst_quoted_strings(*result), sql)
        inner("where x=''", ("where x=@", ['']))
        inner("a'bc'd", ("a@d", ['bc']))
        inner(r"a'bc\\'d", ("a@d", ['bc\\']))
        inner(r"a'\'\\'b''''", ("a@b@@", ['\'\\', '', '']))
        self.assertRaises(AssertionError, mark_quoted_strings, r"a'bc'\\d")
        self.assertRaises(AssertionError, mark_quoted_strings, "a'bc''d")

    def test_simplify_expression(self):
        self.assertEqual(simplify_expression(' a \t b  c . . d '), 'a b c..d')
