import re
from unittest import TestCase

def mark_quoted_strings(sql):
    """Mark all quoted strings in the SOQL by '@' and get them as params,
    with respect to all escaped backslashes and quotes.
    """
    pm_pattern = re.compile(r"'[^\\']*(?:\\[\\'][^\\']*)*'")
    bs_pattern = re.compile(r"\\([\\'])")
    out_pattern = re.compile("^[-!()*+,.:<=>\w\s]*$")
    start = 0
    out = []
    params = []
    for match in pm_pattern.finditer(sql):
        out.append(sql[start:match.start()])
        assert out_pattern.match(sql[start:match.start()])
        params.append(bs_pattern.sub('\\1', sql[match.start() + 1:match.end() -1]))
        start = match.end()
    out.append(sql[start:])
    assert out_pattern.match(sql[start:])
    return '@'.join(out), params

def subst_quoted_strings(sql, params):
    """Reverse operation to mark_quoted_strings - substitutes '@' by params.
    """
    parts = sql.split('@')
    assert len(parts) == len(params) + 1
    out = []
    for i, param in enumerate(params):
        out.append(parts[i])
        out.append("'%s'" % param.replace('\\', '\\\\').replace("\'", "\\\'"))
    out.append(parts[-1])
    return ''.join(out)


def find_closing_parenthesis(sql, startpos):
    """Find the pair of opening and closing parentheses.

    Starts search at the position startpos.
    Returns tuple of positions (opening, closing) if search succeeds, otherwise None.
    """
    pattern = re.compile(r'[()]')
    level = 0
    opening = 0
    for match in pattern.finditer(sql, startpos):
        par = match.group()
        if par == '(':
            if level == 0:
                opening = match.start()
            level += 1
        if par == ')':
            assert level > 0
            level -= 1
            if level == 0:
                closing = match.end()
                return opening, closing

def transform_except_subselect(sql, func):
    """Call a func on every part of SOQL query except nested (SELECT ...)"""
    start = 0
    out = []
    while sql.find('(SELECT', start) > -1:
        pos = sql.find('(SELECT', start)
        out.append(func(sql[start:pos]))
        start, pos = find_closing_parenthesis(sql, pos)
        out.append(sql[start:pos])
        start = pos
    out.append(func(sql[start:len(sql)]))
    return ''.join(out)


class TestSubSelectSearch(TestCase):
    def test_parenthesis(self):
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 0), (0, 2))
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 2), (3, 12))
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 3), (3, 12))
        self.assertEqual(find_closing_parenthesis('() (() (())) ()', 6), (7, 11))
        self.assertEqual(find_closing_parenthesis('() (() (())) ()',13), (13,15))
        self.assertRaises(AssertionError, find_closing_parenthesis, '() (() (())) ()',1)

    def test_subselect(self):
        sql = "SELECT a, (SELECT x FROM y) FROM b WHERE (c IN (SELECT p FROM q WHERE r = %s) AND c = %s)"
        func = lambda sql: '*transfomed*'
        expected =  "*transfomed*(SELECT x FROM y)*transfomed*(SELECT p FROM q WHERE r = %s)*transfomed*"
        self.assertEqual(transform_except_subselect(sql, func), expected)

    def test_nested_subselect(self):
        sql = "SELECT a, (SELECT x, (SELECT p FROM q) FROM y) FROM b"
        func = lambda x: '*transfomed*'
        expected =  "*transfomed*(SELECT x, (SELECT p FROM q) FROM y)*transfomed*"
        self.assertEqual(transform_except_subselect(sql, func), expected)

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
