#!/bin/env python
#
# File format defined in sr24/sr24_doc.pdf.

import codecs
import logging
import os.path
import re
import time

# Definitions for the fields of various tables
#
# N.B. The LANGUAL.NDB_No field is not actually unique, so strip its
#      primary key designation.
#
# N.B. The DATA_SRC.DataSrc_ID field is not unique. In fact, the rows that
#      contain the same ID look like they're just synonyms for eachother.
#      Strip its primary key designation.
#
# TODO: Build an index on LANGUAL.NDB_No, because it looks like it
#       will still be the way people look stuff up.
TABLE_DEFINITIONS = {
'FOOD_DES': [
    ('NDB_No', 'A5*'),
    ('FdGrp_Cd', 'A4'),
    ('LongDesc', 'A200'),
    ('ShrtDesc', 'A60'),
    ('ComName', 'A100'),
    ('ManufacName', 'A65'),
    ('Survey', 'A1'),
    ('Ref_desc', 'A135'),
    ('Refuse', 'N2'),
    ('SciName', 'A65'),
    ('N_Factor', 'N4.2'),
    ('Pro_Factor', 'N4.2'),
    ('Fat_Factor', 'N4.2'),
    ('CHO_Factor', 'N4.2')],
'FD_GROUP' : [
    ('FdGrp_Cd', 'A4*'),
    ('FdGrp_Desc', 'A60')],
'LANGUAL': [
    ('NDB_No', 'A5'),
    ('Factor_Code', 'A5')],
'LANGDESC': [
    ('Factor_Code', 'A5*'),
    ('Description', 'A140')],
'NUT_DATA': [
    ('NDB_No', 'A5*'),
    ('Nutr_No', 'A3*'),
    ('Nutr_Val', 'N10.3'),
    ('Nutr_Data_Pts', 'N5.0'),
    ('Std_Error', 'N8.3'),
    ('Src_Cd', 'A2'),
    ('Deriv_Cd', 'A4'),
    ('Ref_NDB_No', 'A5'),
    ('Add_Nutr_Mark', 'A1'),
    ('Num_Studies', 'N2'),
    ('Min', 'N10.3'),
    ('Max', 'N10.3'),
    ('DF', 'N2'),
    ('Low_EB', 'N10.3'),
    ('Up_EB', 'N10.3'),
    ('Stat_cmt', 'A10'),
    ('AddMod_Date', 'A10'),
    ('CC', 'A1')],
'NUTR_DEF': [
    ('Nutr_No', 'A3*'),
    ('Units', 'A7'),
    ('Tagname', 'A20'),
    ('NutrDesc', 'A60'),
    ('Num_Dec', 'A1'),
    ('SR_Order', 'N6')],
'SRC_CD': [
    ('Src_Cd', 'A2*'),
    ('SrcCd_Desc', 'A60')],
'DERIV_CD': [
    ('Deriv_Cd', 'A4*'),
    ('Deriv_Desc', 'A120')],
'WEIGHT': [
    ('NDB_No', 'A5*'),
    ('Seq', 'A2*'),
    ('Amount', 'N5.3'),
    ('Msre_Desc', 'A80'),
    ('Gm_Wgt', 'N7.1'),
    ('Num_Data_Pts', 'N3'),
    ('Std_Dev', 'N7.3')],
'FOOTNOTE': [
    ('NDB_No', 'A5'),
    ('Footnt_No', 'A4'),
    ('Footnt_Typ', 'A1'),
    ('Nutr_No', 'A3'),
    ('Footnt_Txt', 'A200')],
'DATA_SRC': [
    ('DataSrc_ID', 'A6'),
    ('Authors', 'A255'),
    ('Title', 'A255'),
    ('Year', 'A4'),
    ('Journal', 'A135'),
    ('Vol_City', 'A16'),
    ('Issue_State', 'A5'),
    ('Start_Page', 'A5'),
    ('End_Page', 'A5')]}


def _parse_field_spec(fs):
    '''Return a tuple of (type, width, primary) for the given field
    specification, with 'type' either 'A' or 'N'; 'width' a
    numeric value indicating the number of characters (for 'A' fields)
    or number of digits and decimal places (for 'N' fields); 'primary'
    a boolean indicating whether or not the field is a primary key.
    
    Returns None if the spec could not be parsed.'''

    fs_re = r'^(?P<type>[AN])\s*(?P<width>\d+(\.\d+)?)\s*(?P<primary>\*)?$'

    m = re.match(fs_re, fs)
    if not m:
        return None

    gd = m.groupdict()

    field_type = gd['type']
    field_width = float(gd['width']) if gd['width'].count('.') > 0 \
        else int(gd['width'])
    field_primary = gd['primary'] != None
        
    return (field_type, field_width, field_primary)


def file_records(f, nfields):
    '''A generator function that yields records from the given file as
    tuples. We expect 'nfields' fields for each record; if we don't find
    this, we expect that the record has spanned lines (i.e. contains
    an embedded newline).'''

    class IncompleteFieldError(Exception):
        '''Error to indicate that the last field being mapped to a value
        was incomplete, and that we should join with the next line and
        try again.'''

        pass

    def _field_value(s):
        '''Map a string to a Python value'''

        # An empty value
        if s == '':
            return None

        # A string
        if s[0] == '~':
            if s[-1] != '~':
                raise IncompleteFieldError

            return s[1:-1]

        # A date; these are in the form 'NN/MMM' but do not come with ~s
        # surrounding them despite not being numerical. Aweosome.
        if s.count('/') == 1:
            return s

        # If it's not a string, it had better be a numeric value
        cnt = s.count('.')
        if cnt == 0:
            return int(s)
        elif cnt == 1:
            return float(s)
        else:
            raise Exception('invalid field value: ' + s)

    # Loop through the lines of the file, breaking them into fields for our
    # record and mapping that to Python primitives. Be careful of fields that
    # span mulitple lines, which we handle by keeping an accumulator value
    # of the in-progress record.
    acc = ''
    for l in f:
        fields = (acc + l.strip()).split('^')
        if len(fields) < nfields:
            acc += l
            continue

        assert len(fields) == nfields, 'found too many fields'

        try:
            yield map(_field_value, fields)
            acc = ''
        except IncompleteFieldError:
            acc += l


def populate_db(conn, path):
    '''Populate the given DB-API connection with tables and rows for the NDL
    database files stored at the specified path.
    
    This function has the side-effect of registering a new 'ndldb_busted' codec
    to handle the particular flavor of broken UTF-8 used by the NUTR_DEF.txt
    file to express micrograms.'''

    def _create_table(name, *field_specs):
        '''Create a table with the given field specifications.'''

        cols = []
        primary_keys = []
        for f_name, f_spec in field_specs:
            f_type, f_width, f_primary = _parse_field_spec(f_spec)

            c_name = f_name

            if f_type == 'A':
                c_type = 'varchar(%d)' % f_width
            elif type(f_width) == int:
                c_type = 'number(%d)' % f_width
            else:
                c_type = 'float'

            if f_primary:
                primary_keys += [f_name]

            cols += ['"%s" %s' % (c_name, c_type)]

        if len(primary_keys) > 0:
            cols += ['primary key (%s)' % ', '.join(primary_keys)]
        sql = 'create table "%s" (%s)' % (name, ',\n'.join(cols))

        logging.debug(sql)
        conn.execute(sql)

    def _ndldb_busted_handler(ex):
        assert ex.end - ex.start == 1, 'multi-byte busted char encountered'
        return (unichr(ord(ex.object[ex.start])), ex.end)

    codecs.register_error('ndldb_busted', _ndldb_busted_handler)

    for table_name, table_fields in TABLE_DEFINITIONS.iteritems():
        _create_table(table_name, *table_fields)
        f = codecs.open(
            os.path.join(path, '%s.txt' % table_name), 'r',
            encoding='utf-8', errors='ndldb_busted')

        # Compute the (approximate) number of rows that we're working with so
        # that we can do some more descriptive logging
        nrows = len([l for l in f])
        logging.info('reading %d rows from %s' % (nrows , table_name))
        f.seek(0)

        rownum = 0
        last_log_time = time.time()
        for fr in file_records(f, len(table_fields)):
            rownum += 1
            if rownum % 1000:
                now = time.time()
                if last_log_time < now - 15:
                    last_log_time = now
                    logging.info('added %2.0f%% of rows to table %s' % (
                        float(rownum * 100) / nrows, table_name))

            sql = 'insert into "%s" (%s) values (%s);' % (
                table_name,
                ', '.join(map(lambda x: x[0], table_fields)),
                ', '.join(map(lambda x: '?', range(len(table_fields)))))
            # TODO: This is tripping over the Unicode code point for the micro
            #       symbol (the next character is 'g' for micrograms). Strangely,
            #       this both looks malformed according to UTF-8, and is readable
            #       by vim and rendered correctly.
            logging.debug('%s (%s)' % (
                sql, ', '.join(map(unicode, fr))))
            conn.execute(sql, tuple(fr))

        conn.commit()


if __name__ == '__main__':
    from optparse import OptionParser
    import sqlite3
    import sys

    op = OptionParser(
        usage='%prog [options] <data-path> <sqlite-file>',
        description='''Populate a SQLite database at the given path with the
contents of the NDL data files from the given directory''')
    op.add_option('-v', dest='verbosity', action='count', default=0,
        help='increase logging verbosity; can be used multiple times')

    opts, args = op.parse_args()
    if len(args) < 1:
        op.error('missing path to data files')
    data_path = args[0]

    if len(args) < 2:
        op.error('missing path to SQLite file')
    sql_path = args[1]

    logging.basicConfig(
        stream=sys.stderr,
        format='%(message)s',
        level=logging.ERROR - opts.verbosity * 10)

    populate_db(sqlite3.connect(sql_path), data_path)
