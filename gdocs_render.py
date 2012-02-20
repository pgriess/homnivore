#!/bin/env python
#
# One-off rendering script to render information in the format that I currently
# want it in GDocs. Probably not worth checking in.

import codecs
import fatsecret
import logging
from optparse import OptionParser
import pprint
import re
import recipe
import sys


op = OptionParser(
    usage='''%prog [options] <consumer key> <secret key> <ingredients-file>
                                 <servings>''',
    description='''Read ingredients interactively on stdin (presenting a menu
for clarification in some places and finally write a Nutrition: ... line
to stdout when we're done.''')
op.add_option('-v', dest='verbosity', action='count', default=0,
    help='increase verbosity; can be used multiple times')

opts, args = op.parse_args()

logging.basicConfig(
    stream=sys.stderr,
    format='%(message)s',
    level=logging.CRITICAL - opts.verbosity * 10)

if len(args) < 1:
    op.error('consumer key expected')
if len(args) < 2:
    op.error('secret key expected')
fs = fatsecret.FatSecret(args[0], args[1])

if len(args) < 3:
    op.error('ingredients file expected')
f = codecs.open(args[2], 'r', encoding='utf-8')

if len(args) < 4:
    op.error('number of servings expected')
servings = int(args[3])

ifile = codecs.getreader('utf-8')(sys.stdin)

# Read lines from our recipe file and record the nutrient information for each
# in the 'nutrients' dictinoary
nutrients = {}
for l in f.readlines():
    l = l.strip()
    q, i = recipe.parse_ingredient(l)
    unit, value = q

    # Display the food that we're searching for
    print '<< ' + l

    # Paginate through search results, waiting for the user to select a result
    # for us (or run out of results and abort)
    page_no = 0
    page_sz = 10

    foods = fs.foods_search(
        search_expression=i, page_number=page_no, max_results=page_sz)['foods']
    food_id = None
    while True:
        assert 'food' in foods, \
            'Could not find any more results for ' + i

        foods = foods['food']
        for fn in range(len(foods)):
            print '[%-2.2s] %s' % (str(fn), foods[fn]['food_name'])
            print '     > %s' % foods[fn]['food_description']
        sys.stdout.write('>> [0] ')

        # Ignore EOF, whatever
        cl = sys.stdin.readline().strip()
        choice = None

        if cl == '':
            choice = 0
        elif re.match(r'^\d+$', cl):
            choice = int(cl)

        if choice != None:
            food_id = foods[choice]['food_id']
            break

        if cl == 'n':
            page_no += 1
            foods = fs.foods_search(
                search_expression=i, page_number=page_no,
                max_results=page_sz)['foods']
        else:
            assert False, 'Unknown command: ' + cl

    n = recipe.get_food_nutrition(unit, value, food_id, fs)
    assert n != None, \
        'failed to convert i=%s, food_id=%s' % (i, food_id)

    nutrients[l] = n

# Compute the aggregate nutritional values across all ingredients
total_nutrients = {}
for ni in nutrients.values():
    for n, v in ni.iteritems():
        total_nutrients[n] = total_nutrients.get(n, 0.0) + v

# Compute the percentage that each ingredient contributes to the total for
# each nutrient and log it
for i, ni in nutrients.iteritems():
    logging.error('Nutrition information for: %s' % i.strip())

    for n, v in ni.iteritems():
        pct = v / total_nutrients[n] if total_nutrients[n] > 0 else 0.0
        pct = pct * 100.0
        print '  %s: %.2f%% (%.2f / %.2f)' % (n, pct, v, total_nutrients[n])

# Scale by servings
total_nutrients = dict(
    (n, v / servings) for n, v in total_nutrients.iteritems())

# The order that we want to render nutritents
nutrient_order = [
    'calories',
    'fat',
    'protein',
    'carbohydrate',
    'fiber',
    'cholesterol',
    'iron',
    'sodium',
    'calcium']

def render_nutrient(n):
    val = total_nutrients[n]
    units = fatsecret.units_for_nutrient(n)
    name = n

    # Calories are special -- they're their own units
    if n == 'calories':
        units = ''
        name = 'Calories'

    # If we got a percentage of USRDA as a unit, convert it using
    # the recommended 2000 kcal diet
    if units == '%':
        val = float(val) / 100

        if n == 'vitamin_a':
            units = 'IU'
            val = val * 5000
        elif n == 'vitamin_c':
            units = 'mg'
            val = val * 60
        elif n == 'calcium':
            units = 'mg'
            val = val * 1000
        elif n == 'iron':
            units = 'mg'
            val = val * 18
        else:
            raise Exception('Unknown percentage nutrient: ' + n)

    return '%.1f%s %s' % (val, units, name)

print 'Nutrition: %s' % ', '.join(render_nutrient(n) for n in nutrient_order)
