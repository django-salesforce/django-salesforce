"""Parse SOQL, including subqueries

Subqueries are very restricted by [Force.com SOQL]
(https://resources.docs.salesforce.com/sfdc/pdf/salesforce_soql_sosl.pdf)
(It's lucky for our implementation)
- "only root queries support aggregate expressions"
- Subqueries can not be in "OR" condition, because it is an additional level.

These expressions can be supported here, but currently unimplemented:
    FORMAT(), convertCurrency(), toLabel(),
    Date Functions..., convertTimezone() in Date Functions
    DISTANCE(x, GEOLOCATION(...))
Especially DISTANCE and GEOLOCATION are not trivial because they would
require a combined parser for parentheses and commas.

Unsupported GROUP BY ROLLUP and GROUP BY CUBE (their syntax for reports).
"""
import datetime
import re
import pytz
from salesforce.dbapi.exceptions import ProgrammingError

# reserved wods can not be used as alias names
RESERVED_WORDS = set((
    'AND, ASC, DESC, EXCLUDES, FIRST, FROM, GROUP, HAVING, '
    'IN, INCLUDES, LAST, LIKE, LIMIT, NOT, NULL, NULLS, '
    'OR, SELECT, WHERE, WITH'
).split(', '))
AGGREGATION_WORDS = set((
    'AVG, COUNT, COUNT_DISTINCT, MIN, MAX, SUM'
).split(', '))
pattern_aggregation = re.compile(r'\b(?:{})(?=\()'.format('|'.join(AGGREGATION_WORDS)), re.I)
pattern_groupby = re.compile(r'\bGROUP BY\b', re.I)


class QQuery(object):
    """Parse the SOQL query to an object useful to correctly interpret a response.

    public methods:
        parse_rest_response(records, rowcount, row_type=list):

            Parse the response to rows of the tape list or dict
            parameters:
                records: response['records'] or a slice of its iterator
                rowcount: response['totalSize']

            The `cursor` that created the response can be necessary, but currently unused
    """
    # It can be later splitted to more specialized objects, if QQuery become
    # extended and too complicated.
    # type of query: QRootQuery, QFieldSubquery, QWhereSubquery
    # type of field: QField, QAggregation, QFieldSubquery

    # pylint:disable=too-few-public-methods,too-many-instance-attributes

    def __init__(self, soql=None):
        self.soql = None
        self.fields = []
        # dictionary of chil to parent relationships - lowercase keys
        self.subroots = {}
        self.aliases = []
        self.root_table = None
        # is_aggregation: only to know if aliases are relevant for output
        self.is_aggregation = False
        self.is_count_query = False
        self.has_child_rel_field = False
        # extra_soql: everything what is after the root table name (and
        # after optional alias), usually WHERE...
        self.extra_soql = None
        self.subqueries = None
        if soql:
            self._from_sql(soql)

    def _from_sql(self, soql):
        """Create Force.com SOQL tree structure from SOQL"""
        # pylint:disable=too-many-branches,too-many-nested-blocks
        assert not self.soql, "Don't use _from_sql method directly"
        self.soql = soql
        soql, self.subqueries = split_subquery(soql)
        match_parse = re.match(r'SELECT (.*) FROM (\w+)\b(.*)$', soql, re.I)
        if not match_parse:
            raise ProgrammingError('Invalid SQL: %s' % self.soql)
        fields_sql, self.root_table, self.extra_soql = match_parse.groups()
        fields = [x.strip() for x in fields_sql.split(',')]
        self.is_aggregation = bool(pattern_groupby.search(self.extra_soql) or
                                   pattern_aggregation.search(fields[0]))
        self.is_plain_count = fields[0].upper() == 'COUNT()'
        consumed_subqueries = 0
        expr_alias_counter = 0
        #
        if not self.is_plain_count:
            for field in fields:
                if self.is_aggregation:
                    match = re.search(r'\b\w+$', field)
                    if match:
                        alias = match.group()
                        assert alias not in RESERVED_WORDS, "invalid alias name"
                        if match.start() > 0 and field[match.start() - 1] == ' ':
                            field = field[match.start() - 1]
                    else:
                        alias = 'expr{}'.format(expr_alias_counter)
                        expr_alias_counter += 1
                    assert '&' not in field, "Subquery not expected as field in aggregation query"
                elif '&' in field:
                    assert field == '(&)'  # verify that the subquery was in parentheses
                    subquery = QQuery(self.subqueries[consumed_subqueries][0])
                    consumed_subqueries += 1
                    self.has_child_rel_field = True
                    field = subquery
                    # TODO more child relationships to the same table
                    alias = subquery.root_table
                else:
                    alias = field
                    if '.' in alias:
                        if alias.split('.', 1)[0].lower() == self.root_table.lower():
                            alias = alias.split('.', 1)[1]
                        if '.' in alias:
                            # prepare paths for possible empty outer joins
                            subroots = self.subroots
                            root_crumbs = alias.lower().split('.')[:-1]
                            for scrumb in root_crumbs:
                                subroots.setdefault(scrumb, {})
                                subroots = subroots[scrumb]
                self.aliases.append(alias)
                self.fields.append(field)
        # TODO it is not currently necessary to parse the exta_soql

    def _make_flat(self, row_dict, path, subroots):
        """Replace the nested dict objects by a flat dict with keys "object.object.name"."""
        # can get a cursor parameter, if introspection should be possible on the fly
        out = {}
        for k, v in row_dict.items():
            klc = k.lower()  # "key lower case"
            if (not (isinstance(v, dict) and 'attributes' in v)
                    or ('done' in v and 'records' in v and 'totalSize' in v)):
                # :
                if klc not in subroots:
                    out[klc] = v
                else:
                    strpath = '.'.join(path + (klc,)) + '.'
                    strip_pos = len(strpath) - len(klc + '.')
                    for alias in self.aliases:
                        if alias.lower().startswith(strpath):
                            out[alias.lower()[strip_pos:]] = None  # empty outer join field names
            else:
                new_subroots = subroots[klc] if k != 'attributes' else {}
                for sub_k, sub_v in self._make_flat(v, path + (klc,), new_subroots).items():
                    out[k.lower() + '.' + sub_k] = sub_v
        return out

    def parse_rest_response(self, records, rowcount, row_type=list):
        """Parse the REST API response to DB API cursor flat response"""
        if self.is_plain_count:
            # result of "SELECT COUNT() FROM ... WHERE ..."
            assert list(records) == []
            yield rowcount  # originally [resp.json()['totalSize']]
        else:
            while True:
                for row_deep in records:
                    assert self.is_aggregation == (row_deep['attributes']['type'] == 'AggregateResult')
                    row_flat = self._make_flat(row_deep, path=(), subroots=self.subroots)
                    # TODO Will be the expression "or x['done']" really correct also for long subrequests?
                    assert all(not isinstance(x, dict) or x['done'] for x in row_flat)
                    if issubclass(row_type, dict):
                        yield {k: fix_data_type(row_flat[k.lower()]) for k in self.aliases}
                    else:
                        yield [fix_data_type(row_flat[k.lower()]) for k in self.aliases]
                # if not resp['done']:
                #     if not cursor:
                #         raise ProgrammingError("Must get a cursor")
                #     resp = cursor.query_more(resp['nextRecordsUrl']).json()
                # else:
                #     break
                break


SALESFORCE_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f+0000'
SF_DATETIME_PATTERN = re.compile(r'[1-3]\d{3}-[01]\d-[0-3]\dT[0-2]\d:[0-5]\d:[0-6]\d.\d{3}\+0000$')
TextType = type(u'')


def fix_data_type(data, tzinfo=None):
    # this is a simplified function. The data type should be finally read
    # from some reliable field mapping, not to guess by regexp like here.
    # Only a DateTime field has so specific regexp that the guess is
    # acceptable.
    if isinstance(data, TextType) and SF_DATETIME_PATTERN.match(data):
        datim = datetime.datetime.strptime(data, SALESFORCE_DATETIME_FORMAT)
        datim = datim.replace(tzinfo=tzinfo or pytz.utc)
        return datim
    return data


def mark_quoted_strings(sql):
    """Mark all quoted strings in the SOQL by '@' and get them as params,
    with respect to all escaped backslashes and quotes.
    """
    # pattern of a string parameter (pm), a char escaped by backslash (bs)
    # out_pattern: characters valid in SOQL
    pm_pattern = re.compile(r"'[^\\']*(?:\\[\\'][^\\']*)*'")
    bs_pattern = re.compile(r"\\([\\'])")
    out_pattern = re.compile(r"^(?:[-!()*+,.:<=>\w\s|%s])*$")
    missing_apostrophe = "invalid character in SOQL or a missing apostrophe"
    start = 0
    out = []
    params = []
    for match in pm_pattern.finditer(sql):
        out.append(sql[start:match.start()])
        assert out_pattern.match(sql[start:match.start()]), missing_apostrophe
        params.append(bs_pattern.sub('\\1', sql[match.start() + 1:match.end() - 1]))
        start = match.end()
    out.append(sql[start:])
    assert out_pattern.match(sql[start:]), missing_apostrophe
    return '@'.join(out), params


def subst_quoted_strings(sql, params):
    """Reverse operation to mark_quoted_strings - substitutes '@' by params.
    """
    parts = sql.split('@')
    params_dont_match = "number of parameters doesn' match the transformed query"
    assert len(parts) == len(params) + 1, params_dont_match  # would be internal error
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
    opening = []
    for match in pattern.finditer(sql, startpos):
        par = match.group()
        if par == '(':
            if level == 0:
                opening = match.start()
            level += 1
        if par == ')':
            assert level > 0, "missing '(' before ')'"
            level -= 1
            if level == 0:
                closing = match.end()
                return opening, closing


def transform_except_subquery(sql, func):
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


def split_subquery(sql):
    """Split on subqueries and replace them by '&'."""
    sql, params = mark_quoted_strings(sql)
    sql = simplify_expression(sql)
    _ = params  # NOQA
    start = 0
    out = []
    subqueries = []
    pattern = re.compile(r'\(SELECT\b', re.I)
    match = pattern.search(sql, start)
    while match:
        out.append(sql[start:match.start() + 1] + '&')
        start, pos = find_closing_parenthesis(sql, match.start())
        start, pos = start + 1, pos - 1
        subqueries.append(split_subquery(sql[start:pos]))
        start = pos
        match = pattern.search(sql, start)
    out.append(sql[start:len(sql)])
    return ''.join(out), subqueries


def simplify_expression(txt):
    """Remove all unecessary whitespace and some very usual space"""
    minimal = re.sub(r'\s', ' ',
                     re.sub(r'\s(?=\W)', '',
                            re.sub(r'(?<=\W)\s', '',
                                   txt.strip())))
    # add space before some "(" and after some ")"
    return re.sub(r'\)(?=\w)', ') ',
                  re.sub(r'(,|\b(?:{}))\('.format('|'.join(RESERVED_WORDS)), '\\1 (', minimal)
                  )
