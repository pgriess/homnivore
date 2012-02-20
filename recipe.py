#!/bin/env python
# vim: set fileencoding=utf-8
#
# Scrape nutrition information from a recipe.
#
# Recipe ingredients must be formatted according to the following rules
#
#   - Start with a quantity (e.g. '1 tbsp'). Unicode vulgar fractions are
#     supported. Units have a trailig '.' or 's' stripped in an attempt
#     to normalize things.
#
#   - Anything in parenthesis is ignored. This should allow approximations and
#     other non-parsable content to be used (e.g. '1 tbsp (about 2 whole)
#     cloves').
#
#   - Anything after a comma is considered preparation directions and is
#     discarded (e.g. '4 cloves garlic, thinly sliced'). Without this, such
#     search terms can surface other foods (e.g. thinly sliced roast beef) by
#     overpowering the real ingredient.
#
#   - Everything else is considered a search term for the ingredient. The first
#     result is selected.

from fatsecret import FatSecret
import logging
import pprint
import re
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

# Conversion of different mass units to grams
MASS_CONSTANTS = {
    'lb': 453.6,
    'lb.': 453.6,
    'lbs': 453.6,
    'lbs.': 453.6,
    'pound': 453.6,
    'pounds': 453.6,
    'oz': 28.3,
    'oz.': 28.3,
    'ozs': 28.3,
    'ozs.': 28.3,
    'ounce': 28.3,
    'ounces': 28.3,
    'g': 1.0,
    'gs': 1.0,
    'gs.': 1.0,
    'gram': 1.0,
    'grams': 1.0}

# Conversion of different volume units to ml
VOLUME_CONSTANTS = {
    'tbsp': 14.79,
    'tbsp.': 14.79,
    'tbsps': 14.79,
    'tbsps.': 14.79,
    'tablespoon': 14.79,
    'tablespoons': 14.79,
    'cup': 236.59,
    'cups': 236.59,
    'tsp': 4.93,
    'tsp.': 4.93,
    'tsps': 4.93,
    'tsps.': 4.93,
    'teaspoon': 4.93,
    'ml': 1.0,
    'oz': 29.57,
    'oz.': 29.57,
    'ozs': 29.57,
    'ozs.': 29.57,
    'ounce': 29.57,
    'ounces': 29.57}

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

    raise Exception('Unknown input format for numeric quantity: ' + s)


def parse_quantity(s):
    '''
    Parse the quantity at the beginning of a string. Returns a tuple of ((type,
    value) (begin, end)), where type is a string describing the unit in
    question, value is a numeric value, and (begin, end) is the region in the
    input string where the quantity was found. Common/recognized units are
    normalized if possible (e.g. pounds will be converted to grams).
    '''

    nv, nr = parse_numeric_quantity(s)

    # Matches '23 fribfrabs.'
    #
    # Note that we cannot use r'\b' as a terminator becuase that prevents us
    # from matching a trailing '.'. Also we are careful not to allow a trailing
    # 's' character on our unit so that if there is one, it gets consumed by
    # the pluralization/abbreviation class at the end.
    RE = re.compile(r'\s*(([a-zA-Z]+[a-rt-zA-RT-Z])[\.s]{0,2})\s*', re.UNICODE)
    m = RE.match(s, nr[1])
    if m:
        unit = m.group(2)
        if unit in MASS_CONSTANTS:
            q = ('g', nv * MASS_CONSTANTS[unit])
        elif unit in VOLUME_CONSTANTS:
            q = ('ml', nv * VOLUME_CONSTANTS[unit])
        else:
            q = (unit, nv)

        return (q, (nr[0], m.end(1)))

    raise Exception('Unknown input format for quantity: ' + s[nr[1]:])


def parse_ingredient(s):
    '''
    Parse an ingredient specification into an ((type, value), ingredient)
    tuple.

    The (type, value) tuple is just like that given in the first element of the
    parse_quantity() return value. The 'ingredient' value is a string
    indicating our best guess as to the ingredient in question.
    '''

    # Strip any parenthesized content
    s = re.sub(r'\([^)]*\)', '', s)
    s = re.sub(r'\s{2,}', ' ', s)
    s = s.strip()

    # Strip content after a comma
    if ',' in s:
        s = s[:s.find(',')]

    q, r = parse_quantity(s)
    return (q, s[r[1]:].strip())


def get_food_nutrition(unit, value, food_id):
    '''
    Return a dictionary of nutrition information for the given quantity a of
    the food described by food_id. If no suitable conversion could be found,
    None is returned.
    '''

    def gen_wrap_f(x):
        if type(x) == list:
            for xx in x:
                yield xx
        else:
            yield x

    def convert_units(s_unit, s_val):
        if s_unit in MASS_CONSTANTS and unit in MASS_CONSTANTS:
            u_val = MASS_CONSTANTS[s_unit] * s_val
            q_val = MASS_CONSTANTS[q[0]] * value
            return q_val / u_val

        if s_unit in VOLUME_CONSTANTS and unit in VOLUME_CONSTANTS:
            u_val = VOLUME_CONSTANTS[s_unit] * s_val
            q_val = VOLUME_CONSTANTS[unit] * value
            return q_val / u_val

        return None

    def scale_serving(serv):
        scale_val = None

        def scale_ingredient(k, v):
            try:
                if not k.endswith('_id'):
                    return (k, float(v) * scale_val)
                else:
                    return (k, v)
            except ValueError:
                return (k, v)

        # Prefer metric serving units that we can convert between eachother.
        # For example, grams to oz, etc. This is the mostly directly comparable
        # and fool-proof computation.
        scale_val = convert_units(
            serv['metric_serving_unit'],
            float(serv['metric_serving_amount']))

        # If we couldn't use the metric units, try the units from the measurement
        # description (which may be different). A common example of this is the
        # metric unit being grams and the measurement description being cups or
        # tbsp or something. Since we don't have a conersion between mass to volume
        # we just try the other unit.
        if scale_val == None:
            s_unit = serv['measurement_description']
            s_unit = re.sub(r'\([^)]*\)', '', s_unit)
            s_unit = re.sub(r'\s{2,}', ' ', s_unit)
            s_unit = s_unit.strip()
            s_val = float(serv['number_of_units'])

            scale_val = convert_units(s_unit, s_val)

            # If that didn't work, it's because either the user's unit or the
            # unit from FatSecret wasn't in our conversion table. See if
            # they're equal (e.g. 'medium') and go with it.
            if scale_val == None and s_unit == unit:
                scale_val = value / s_val

        if scale_val == None:
            return None

        # Scale the nutritional information by our scaling factor
        return dict([scale_ingredient(k, v) for k, v in serv.iteritems()])

    food = fs.food_get(food_id=food_id)
    servings = food['food']['servings']['serving']
    if type(servings) == list:
        for s in servings:
            logging.debug(pprint.pformat(s))

            ss = scale_serving(s)
            if ss != None:
                return ss
    else:
        return scale_serving(servings)


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
        self.assertEquals(('g', MASS_CONSTANTS['lb']), q)
        self.assertEquals((0, 6), r)

        q, r = parse_quantity('2.5 oz biff')
        self.assertEquals(('g', 2.5 * MASS_CONSTANTS['oz']), q)
        self.assertEquals((0, 6), r)

    def test_volume(self):
        q, r = parse_quantity(u'1 \u215D cups of chicken broth')
        self.assertEquals(('ml', 1.625 * VOLUME_CONSTANTS['cup']), q)
        self.assertEquals((0, 8), r)

        q, r = parse_quantity(u'\u00bc tsp of chicken broth')
        self.assertEquals(('ml', 0.25 * VOLUME_CONSTANTS['tsp']), q)
        self.assertEquals((0, 5), r)

    def test_unknown(self):
        q, r = parse_quantity('4 cloves garlic')
        self.assertEquals(('clove', 4), q)
        self.assertEquals((0, 8), r)


class _IngredientTestCase(unittest.TestCase):

    def test_simple(self):
        q, i = parse_ingredient('1 clove garlic')
        self.assertEquals(('clove', 1), q)
        self.assertEquals('garlic', i)


class _NutritionTestCase(unittest.TestCase):
    
    def setUp(self):
        import os

        self.fs = FatSecret(
            consumerKey=os.environ['FS_CONSUMER_KEY'],
            secretKey=os.environ['FS_SECRET_KEY'])

    def test_single(self):
        ni = get_ingredient_nutrition('1 clove garlic', self.fs)
        self.assertEquals(ni['calories'], 4)
        self.assertEquals(ni['protein'], 0.19)

    def test_scale(self):
        ni = get_ingredient_nutrition('2 cloves garlic', self.fs)
        self.assertEquals(ni['calories'], 8)
        self.assertEquals(ni['protein'], 0.38)


if __name__ == '__main__':
    import codecs
    from optparse import OptionParser
    import sys

    op = OptionParser(
        usage='%prog [options] <consumer key> <secret key>',
        description='''Reads recipe ingredients from stdin, one at a time, and
writes total nutrition information for the recipe to stdout. The keys
specified are to be used for the FatSecret API.''')
    op.add_option('-i', dest='infile', default='-',
        help='read from the specified file (default: %default)')
    op.add_option('-o', dest='outfile', default='-',
        help='write to the specified file (default: %default)')
    op.add_option('-v', dest='verbosity', action='count', default=0,
        help='increase verbosity; can be used multiple times')
    
    opts, args = op.parse_args()

    logging.basicConfig(
        stream=sys.stderr,
        format='%(message)s',
        level=logging.CRITICAL - opts.verbosity * 10)

    if len(args) < 1:
        op.error('missing consumer key')
    consumerKey = args[0]

    if len(args) < 2:
        op.error('missing secret key')
    secretKey = args[1]

    ifile = sys.stdin if opts.infile == '-' \
        else open(opts.infile, 'r')
    istream = codecs.getreader('utf-8')(ifile)
    ofile = sys.stdout if opts.outfile == '-' \
        else open(opts.outfile, 'w')
    ostream = codecs.getwriter('utf-8')(ofile)

    fs = FatSecret(consumerKey, secretKey)

    for l in istream.readlines():
        q, i = parse_ingredient(l)
        unit, value = q

        foods = fs.foods_search(search_expression=i)['foods']
        if foods['total_results'] == 0:
            print >> sys.stderr, 'No matches for ' + i
            sys.exit(1)

        foods = foods['food']
        if opts.infile == '-' or opts.outfile == '-':
            food_id = foods[0]['food_id']
        else:
            print i

            for i in range(len(foods)):
                print '[%d] %s' % (i, foods[i]['food_name'])
            sys.stdout.write('>> ')
            choice = int(sys.stdin.readline().strip())
            food_id = foods[choice]['food_id']

        n = get_food_nutrition(unit, value, food_id)
        logging.info(pprint.pformat(n))
