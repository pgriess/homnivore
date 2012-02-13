#!/bin/env python
# vim: set fileencoding=utf-8
#
# Scrape nutrition information from a recipe.

import re
from string import whitespace
import unittest

# Conversion of Unicode characters to their floating point values
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

MASS = 1
VOLUME = 2

# Conversion of different mass units to grams
MASS_CONSTANTS = {
    'lb': 453.6,
    'oz': 28.3,
    'g': 1.0,
    'mg': 0.001}

# Conversion of different volume units to floz
VOLUME_CONSTANTS = {
    'tbsp': 0.5,
    'tsp': 0.17,
    'cup': 8.0}

def parse_numeric_quantity(s):
    '''
    Parse the numeric quantity at the beginning of a string. Returns a tuple of
    (value, (begin, end)), where 'value' is the value as a float (without
    units), and the (begin, end) tuple indicates the region of the input string
    that was considered to describe the quantity.
    '''

    # Matches '23 ½'
    VULGAR_FRACTION_RE = re.compile(
        r'\s*(?P<digits>\d+)?\s*(?P<fraction>[%s])\b' % \
            '|'.join(UNICODE_VULGAR_FRACTIONS),
        re.UNICODE)
    m = VULGAR_FRACTION_RE.match(s)
    if m:
        gd = m.groupdict()
        v = UNICODE_VULGAR_FRACTIONS[gd['fraction']]
        if gd['digits']:
            v += float(gd['digits'])

        return (v, m.span())

    # Matches '23.5'
    DECIMAL_RE = re.compile(r'\s*\d+(\.\d+)?\b', re.UNICODE)
    m = DECIMAL_RE.match(s)
    if m:
        return (float(s[:m.end()]), m.span())

    raise Exception('Unknown input format for numeric quantity')


def parse_quantity(s):
    '''
    Parse the quantity at the beginning of a string. Returns a tuple of ((type,
    value) (begin, end)), where type is either MASS or VOLUME, value is a
    numeric value, and (begin, end) is the region in the input string where the
    quantity was found.
    '''

    nv, nr = parse_numeric_quantity(s)

    # Matches '23 lbs.'
    #
    # Note that we cannot use r'\b' as a terminator becuase that prevents us
    # from matching a trailing '.'.
    MASS_RE = re.compile(
        r'\s*((%s)[\.s]{0,2})\s+' % '|'.join(MASS_CONSTANTS),
        re.UNICODE)
    m = MASS_RE.match(s, nr[1])
    if m:
        return (
            (MASS, nv * MASS_CONSTANTS[m.group(2)]),
            (nr[0], m.end(1)))

    # Matches '23 tbsps.'
    VOLUME_RE = re.compile(
        r'\s*((%s)[\.s]{0,2})\s+' % '|'.join(VOLUME_CONSTANTS),
        re.UNICODE)
    m = VOLUME_RE.match(s, nr[1])
    if m:
        return (
            (VOLUME, nv * VOLUME_CONSTANTS[m.group(2)]),
            (nr[0], m.end(1)))

    raise Exception('Unknown input format for quantity')


class _NumericQuantityTestCase(unittest.TestCase):

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
        q, r = parse_numeric_quantity(u'\u00bc larf biff')
        self.assertEquals(0.25, q)
        self.assertEquals((0, 1), r)

        q, r = parse_numeric_quantity(u'1 \u00be larf biff')
        self.assertEquals(1.75, q)
        self.assertEquals((0, 3), r)


class _QuantityTestCase(unittest.TestCase):

    def test_mass(self):
        q, r = parse_quantity('1 lbs. larf')
        self.assertEquals((MASS, MASS_CONSTANTS['lb']), q)
        self.assertEquals((0, 6), r)

        q, r = parse_quantity('2.5 oz biff')
        self.assertEquals((MASS, 2.5 * MASS_CONSTANTS['oz']), q)
        self.assertEquals((0, 6), r)

    def test_volume(self):
        q, r = parse_quantity('1 cup of chicken broth')
        self.assertEquals((VOLUME, VOLUME_CONSTANTS['cup']), q)
        self.assertEquals((0, 5), r)

        q, r = parse_quantity(u'\u00bc tsp of chicken broth')
        self.assertEquals((VOLUME, 0.25 * VOLUME_CONSTANTS['tsp']), q)
        self.assertEquals((0, 5), r)


if __name__ == '__main__':
    unittest.main()
