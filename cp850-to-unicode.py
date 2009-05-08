#!/usr/bin/env python
"""
Converts a QwkWeb SQLite database in cp850 encoding to unicode.
"""
import sys
from sqlite3 import dbapi2 as sqlite


def sqlquote(value):
    """
    Quote for SQL and convert cp850 to unicode.
    """
    if isinstance(value, str):
        value = unicode(value, 'cp850')
    if isinstance(value, basestring):
        return u"'%s'" % value.replace(u"'", u"''")
    elif isinstance(value, (int, long, float)):
        return value


def main(argv):
    if len(argv) != 3:
        print >> sys.stderr, "Syntax: %s old.db new.db" % argv[0]
        print >> sys.stderr, "New db must exist but have no contents."

    con1 = sqlite.connect(argv[1])
    con1.text_factory = str
    cur1 = con1.cursor()
    con2 = sqlite.connect(argv[2])
    cur2 = con2.cursor()

    # Convert table board
    cur1.execute('SELECT id, title FROM board')
    for result in cur1.fetchall():
        cur2.execute(u'INSERT INTO board (id, title) VALUES (%s, %s)' %
                     tuple([sqlquote(x) for x in result]))
    # Convert for table forum
    cur1.execute('SELECT id, boardid, title FROM forum')
    for result in cur1.fetchall():
        cur2.execute(u'INSERT into forum (id, boardid, title) VALUES '\
                     u'(%s, %s, %s)' % tuple(
                         [sqlquote(x) for x in result]))
    # Convert for table message
    cur1.execute('SELECT id, forumid, boardid, mdate, mtime, mto, mfrom, reference, subject, body FROM message')
    for result in cur1.fetchall():
        cur2.execute(u'INSERT into message (id, forumid, boardid, mdate, mtime, mto, mfrom, reference, subject, body) VALUES '\
                     u'(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)' % tuple(
                         [sqlquote(x) for x in result]))
    con2.commit()
    con2.close()

if __name__ == '__main__':
    sys.exit(main(sys.argv))
