#!/bin/env python
#
# Full-text search for recipe ingredients. Uses Xapian.

import logging
import xapian

if __name__ == '__main__':
    from optparse import OptionParser
    import sqlite3
    import sys

    op = OptionParser(
        usage='%prog [options] <xapian-db> <sqlite_db>',
        description='''Perform ingredient-related operations on the given
Xapian database. One of either the -w or -q options must be specified.''')
    op.add_option('-w', dest='write', action='store_true',
        default=False,
        help='''write the contents of the SQLite database to the Xapian
database (default: %default)''')
    op.add_option('-q', dest='query', metavar='<query>', default=None,
        help='query the Xapian database with <query>')
    op.add_option('-v', dest='verbosity', action='count', default=0,
        help='increase logging verbosity; can be used multiple times')
    
    opts, args = op.parse_args()

    if len(args) < 1:
        op.error('missing path to Xapian database')
    xdb_path = args[0]

    if len(args) < 2:
        op.error('missing path to SQLite database')
    sdb_path = args[1]

    if not opts.write and not opts.query:
        op.error('one of either -w or -q must be specified')

    logging.basicConfig(
        stream=sys.stderr,
        format='%(message)s',
        level=logging.ERROR - opts.verbosity * 10)

    sdb = sqlite3.connect(sdb_path)

    if opts.write:
        xdb = xapian.WritableDatabase(xdb_path, xapian.DB_CREATE_OR_OVERWRITE)
        xtg = xapian.TermGenerator()
        xtg.set_stemmer(xapian.Stem('english'))

        for ndb_no, long_desc in \
            sdb.execute('select NDB_No, LongDesc from FOOD_DES'):
            doc = xapian.Document()
            xtg.set_document(doc)

            doc.set_data(ndb_no)
            xtg.index_text(long_desc, 1)

            xdb.add_document(doc)

        xdb.commit()
    else:
        xdb = xapian.Database(xdb_path)

        xqp = xapian.QueryParser()
        xqp.set_stemmer(xapian.Stem('english'))
        xqp.set_stemming_strategy(xapian.QueryParser.STEM_SOME)
        xqp.set_database(xdb)

        xq = xqp.parse_query(opts.query)

        xe = xapian.Enquire(xdb)
        xe.set_query(xq)
        for m in xe.get_mset(0, 9999):
            for r in sdb.execute('select * from FOOD_DES where NDB_No = ?', [m.document.get_data()]):
                long_desc = r[2]

                print long_desc
