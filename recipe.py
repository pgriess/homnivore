#!/bin/env python
# vim: set fileencoding=utf-8
#
# Scrape nutrition information from a recipe.

import re
from string import whitespace
import unittest

def parse_numeric_quantity(s):
    '''
    Parse the numeric quantity at the beginning of a string. Returns a tuple of
    (value, (begin, end)), where 'value' is the value as a float (without
    units), and the (begin, end) tuple indicates the region of the input string
    that was considered to describe the quantity.
    '''

    UNICODE_VULGAR_FRACTIONS = {
        u'\u00bc': 1.0/4,
        u'\u00bd': 1.0/2,
        u'\u00be': 3.0/4,
        u'\u2150': 1.0/7,
        u'\u2151': 1.0/9,
        u'\u2152': 1.0/10,
        u'\u2153': 1.0/3,
        u'\u2154': 2.0/3,
        u'\u2155': 1.0/5,
        u'\u2156': 2.0/5,
        u'\u2157': 3.0/5,
        u'\u2158': 4.0/5,
        u'\u2159': 1.0/6,
        u'\u215A': 5.0/6,
        u'\u215B': 1.0/8,
        u'\u215C': 3.0/8,
        u'\u215D': 5.0/8,
        u'\u215E': 7.0/8}

    r = r'(^\s*\d+(\.\d+)?)?\s*([%s])\b' % '|'.join(UNICODE_VULGAR_FRACTIONS)
    m = re.match(r, s, re.UNICODE)
    if m:
        return (
            float(m.group(1)) + UNICODE_VULGAR_FRACTIONS[m.group(3)],
            (m.start(), m.end()))

    m = re.match(r'^\s*\d+(\.\d+)?\b', s, re.UNICODE)
    if m:
        return (
            float(s[:m.end()]),
            (m.start(), m.end()))

    raise Exception('unknown input format')


class _QuantityTestCase(unittest.TestCase):

    def test_simple(self):
        q, r = parse_numeric_quantity('1 larf')
        self.assertEquals(1.0, q)
        self.assertEquals((0, 1), r)

        q, r = parse_numeric_quantity('12 larf')
        self.assertEquals(12.0, q)
        self.assertEquals((0, 2), r)

        q, r = parse_numeric_quantity('12.5 larf 1 harf')
        self.assertEquals(12.5, q)
        self.assertEquals((0, 4), r)

    def test_unicode(self):
        q, r = parse_numeric_quantity(u'1 \u00be larf biff')
        self.assertEquals(1.75, q)
        self.assertEquals((0, 3), r)


if __name__ == '__main__':
    unittest.main()
