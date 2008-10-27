#!/usr/bin/env python

import os.path
from base64 import b64decode
import ConfigParser
from StringIO import StringIO
import web
from qwk import QwkMessage, QwkPacket

render = web.template.render('templates/')

config = ConfigParser.ConfigParser()
config.read(['.qwkweb.conf', os.path.expanduser('~/.qwkweb.conf'),
             '/etc/qwkweb.conf'])

web.config.db_parameters = {}
for key, value in config.items('qwkweb'):
    web.config.db_parameters[key] = value

urls = (
    '/', 'Index',
    '/search', 'Search',
    '/upload', 'Upload',
    '/(.*)/(.*)/(.*)/?', 'ViewMessage',
    '/(.*)/(.*)/?', 'ForumIndex',
    '/(.*)/?', 'BoardIndex',
    )


def unauthorized():
    """
    Ask user to login.
    """
    web.ctx.status = '401 Unauthorized'
    web.header('WWW-Authenticate', 'Basic realm="BBS Archives"')

def auth():
    """
    Return True if authorised, False if not.
    """
    if 'HTTP_AUTHORIZATION' in web.ctx.env.keys():
        hdr = web.ctx.env['HTTP_AUTHORIZATION']
    else:
        hdr = None

    if hdr:
        if (hdr[0:5] != 'Basic'):
            web.badrequest()
        username, password = b64decode(hdr[6:].strip()).split(':')
        if username == password == 'archives':
            return True
    return False

def sqlquote(value):
    """
    web.sqlquote does strange things, so we make our own version.
    """
    if isinstance(value, basestring):
        return "'%s'" % value.replace("'", "''")
    elif isinstance(value, [int, long, float]):
        return value

class Index:
    """
    QwkWeb index page.
    """
    def GET(self):
        bbsnames = web.select('board', order='id')
        web.header('Content-Type', 'text/html; charset=cp850')
        print render.index(list(bbsnames))

class Search:
    """
    Search for a message.
    """
    def GET(self):
        if not auth():
            unauthorized()
            web.header('Content-Type', 'text/html; charset=cp850')
            print render.unauthorized()
            return

        form = web.input(start=0, size=100, order='id',
                         board='', mfrom='', mto='', subject='', body='')
        start = int(form.start)
        size = int(form.size)
        order = form.order

        board = form.board
        mfrom = form.mfrom.strip()
        mto = form.mto.strip()
        subject = form.subject.strip()
        body = form.body.strip()

        query = []
        if board:
            query.append("boardid = %s" % sqlquote(board))
        if mfrom:
            query.append("mfrom LIKE %s" % sqlquote('%'+mfrom+'%'))
        if mto:
            query.append("mto LIKE %s" % sqlquote('%'+mto+'%'))
        if subject:
            query.append("subject LIKE %s" % sqlquote('%'+subject+'%'))
        if body:
            query.append("body LIKE %s" % sqlquote('%'+body+'%'))
        squery = ' AND '.join(query)

        mcount = web.select('message',
                            where=squery,
                            what='count(*) as count')[0].count

        # XXX: SQLite hack to handle non-UTF-8 text. May not work with other databases.
        web.ctx.db.text_factory = str

        messages = web.select('message', locals(),
                              where=squery,
                              what='id, boardid, forumid, mdate, mtime, mfrom, mto, subject',
                              offset='$start',
                              limit='$size',
                              order='$order')
        if start == 0:
            prevstart = None
        else:
            prevstart = max(0, start-size)
        if start+size < mcount:
            nextstart = start+size
        else:
            nextstart = None

        web.header('Content-Type', 'text/html; charset=cp850')
        print render.search(mcount, list(messages),
                            board, mfrom, mto, subject, body,
                            order, size, prevstart=prevstart, nextstart=nextstart)

class Upload:
    """
    Handle an uploaded QWK packet.
    """
    def POST(self):
        form = web.input()
        qwkfile = form.qwkfile
        print "Parsing packet..."
        qwk = QwkPacket(StringIO(qwkfile))

        # Register the BBS if not previously known
        bbsid = qwk.bbsid.lower()
        print "BBS: %s: %s" % (bbsid, qwk.bbsname)
        if web.select('board', locals(), what='count(*) as count',
                      where='id = $bbsid')[0].count == 0:
            web.insert('board', id=bbsid, title=qwk.bbsname)

        # Parse messages per forum
        for forum in qwk.forums:
            forumtitle = qwk.forums[forum]['title']
            if web.select('forum', locals(), what='count(*) as count',
                          where='id = $forum AND boardid = $bbsid')[0].count == 0:
                print "Registering new forum: %d: %s" % (forum, forumtitle)
                web.insert('forum', id=forum, boardid=bbsid, title=forumtitle)
            for message in qwk.forums[forum]['messages']:
                msgno = message.number
                if message.private:
                    print "Discarded private message %d." % msgno
                    continue
                if web.select('message', locals(), what='count(*) as count',
                              where='id = $msgno AND forumid = $forum AND boardid = $bbsid'
                              )[0].count == 0:
                    # Message not in archive already. Insert it.
                    print "Message %d in forum %d %s (%s %s/%s/%s/%s)." % (
                        msgno, forum, forumtitle, message.date, message.time, message.mfrom, message.mto, message.subject)
                    web.insert('message',
                               id = msgno,
                               forumid = forum,
                               boardid = bbsid,
                               mdate = message.date,
                               mtime = message.time,
                               mfrom = message.mfrom,
                               mto = message.mto,
                               reference = message.reference,
                               subject = message.subject,
                               body = message.body
                               )
                else:
                    print "Ignoring duplicate message %d in forum %d %s." % (msgno, forum, forumtitle)
        print "Done."

class BoardIndex:
    """
    List available forums in a given BBS.
    """
    def GET(self, board):
        if not auth():
            unauthorized()
            web.header('Content-Type', 'text/html; charset=cp850')
            print render.unauthorized()
            return
        boardnames = web.select('board', locals(), where='id = $board')
        if not boardnames:
            print "Unknown board."
            return
        boardname = boardnames[0].title
        forums = web.select('forum', locals(), where='boardid = $board', order='id')
        web.header('Content-Type', 'text/html; charset=cp850')
        print render.forumlist(board, boardname, list(forums))

class ForumIndex:
    """
    List all messages in a given forum. Paginate.
    """
    def GET(self, board, forum):
        if not auth():
            unauthorized()
            web.header('Content-Type', 'text/html; charset=cp850')
            print render.unauthorized()
            return

        form = web.input(start=0, size=100, order='id')
        start = int(form.start)
        size = int(form.size)
        order = form.order
        forum = int(forum)
        boardnames = web.select('board', locals(), where='id = $board')
        if not boardnames:
            print "Unknown board."
            return
        boardname = boardnames[0].title
        forumnames = web.select('forum', locals(), where='id = $forum AND boardid = $board')
        if not forumnames:
            print "Unknown forum."
            return
        forumname = forumnames[0].title

        # XXX: SQLite hack to handle non-UTF-8 text. May not work with other databases.
        web.ctx.db.text_factory = str

        # TODO: No pagination yet. Surely there is an elegant way to do this?
        mcount = web.select('message', locals(),
                            where='boardid = $board AND forumid = $forum',
                            what='count(*) as count')[0].count
        messages = web.select('message', locals(),
                              where='boardid = $board AND forumid = $forum',
                              what='id, mdate, mtime, mfrom, mto, subject',
                              offset='$start',
                              limit='$size',
                              order='$order')
        if start == 0:
            prevstart = None
        else:
            prevstart = max(0, start-size)
        if start+size < mcount:
            nextstart = start+size
        else:
            nextstart = None

        web.header('Content-Type', 'text/html; charset=cp850')
        print render.messagelist(board, boardname, forum, forumname, list(messages),
                                 order, size, prevstart=prevstart, nextstart=nextstart)

class ViewMessage:
    """
    View a message from a given board and forum.
    """
    def GET(self, board, forum, msgno):
        if not auth():
            unauthorized()
            web.header('Content-Type', 'text/html; charset=cp850')
            print render.unauthorized()
            return
        forum = int(forum)
        msgno = int(msgno)
        boardnames = web.select('board', locals(), where='id = $board')
        if not boardnames:
            print "Unknown board."
            return
        boardname = boardnames[0].title
        forumnames = web.select('forum', locals(), where='id = $forum AND boardid = $board')
        if not forumnames:
            print "Unknown forum."
            return
        forumname = forumnames[0].title
        # Retrieve and display message.
        # XXX: SQLite hack to handle non-UTF-8 text. May not work with other databases.
        web.ctx.db.text_factory = str
        messages = list(web.select('message', locals(),
                       where='id = $msgno AND forumid = $forum AND boardid = $board'))
        if len(messages) != 1:
            print "No such message."
            return
        message = messages[0]
        if not message.reference:
            reference = None
        else:
            refno = message.reference
            references = list(web.select('message', locals(),
                        where='id = $refno AND forumid = $forum AND boardid = $board'))
            if len(references) > 0:
                reference = references[0]
            else:
                reference = None
        followups = list(web.select('message', locals(),
                        where='reference = $msgno AND forumid = $forum AND boardid = $board'))
        prevmsgs = list(web.select('message', locals(),
                        what='id, mfrom, mto, subject',
                        where='boardid = $board AND forumid = $forum AND id < $msgno',
                        order='id DESC', limit=1))
        if prevmsgs:
            prevmsg = prevmsgs[0]
        else:
            prevmsg = None
        nextmsgs = list(web.select('message', locals(),
                        what='id, mfrom, mto, subject',
                        where='boardid = $board AND forumid = $forum AND id > $msgno',
                        order='id ASC', limit=1))
        if nextmsgs:
            nextmsg = nextmsgs[0]
        else:
            nextmsg = None
        web.header('Content-Type', 'text/html; charset=cp850')
        print render.message(board, boardname, forum, forumname, message, reference, followups,
                             prevmsg, nextmsg)


web.webapi.internalerror = web.debugerror
application = web.wsgifunc(web.webpyfunc(urls, globals()))

if __name__ == '__main__':
    web.run(urls, globals(), web.reloader)
