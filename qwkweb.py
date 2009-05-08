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

db_parameters = {}
for key, value in config.items('qwkweb'):
    db_parameters[key] = value
db = web.database(**db_parameters)

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
    elif isinstance(value, (int, long, float)):
        return value

class Index:
    """
    QwkWeb index page.
    """
    def GET(self):
        bbsnames = db.select('board', order='id')
        web.header('Content-Type', 'text/html; charset=utf-8')
        return render.index(list(bbsnames))

class Search:
    """
    Search for a message.
    """
    def GET(self):
        if not auth():
            unauthorized()
            web.header('Content-Type', 'text/html; charset=utf-8')
            return render.unauthorized()

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

        mcount = db.select('message',
                            where=squery,
                            what='count(*) as count')[0].count

        messages = db.select('message', locals(),
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

        web.header('Content-Type', 'text/html; charset=utf-8')
        return render.search(mcount, list(messages),
                            board, mfrom, mto, subject, body,
                            order, size, prevstart=prevstart, nextstart=nextstart)

class Upload:
    """
    Handle an uploaded QWK packet.
    """
    def POST(self):
        form = web.input()
        qwkfile = form.qwkfile
        yield "Parsing packet..."
        qwk = QwkPacket(StringIO(qwkfile))

        # Register the BBS if not previously known
        bbsid = unicode(qwk.bbsid.lower(), 'cp850')
        yield "BBS: %s: %s" % (bbsid, qwk.bbsname)
        if db.select('board', locals(), what='count(*) as count',
                      where='id = $bbsid')[0].count == 0:
            db.insert('board', id=bbsid, title=unicode(qwk.bbsname, 'cp850'))

        # Parse messages per forum
        for forum in qwk.forums:
            forumtitle = unicode(qwk.forums[forum]['title'], 'cp850')
            if db.select('forum', locals(), what='count(*) as count',
                          where='id = $forum AND boardid = $bbsid')[0].count == 0:
                yield "Registering new forum: %d: %s" % (forum, forumtitle)
                db.insert('forum', id=forum, boardid=bbsid, title=forumtitle)
            for message in qwk.forums[forum]['messages']:
                msgno = message.number
                if message.private:
                    yield "Discarded private message %d." % msgno
                    continue
                if db.select('message', locals(), what='count(*) as count',
                              where='id = $msgno AND forumid = $forum AND boardid = $bbsid'
                              )[0].count == 0:
                    # Message not in archive already. Insert it.
                    yield "Message %d in forum %d %s (%s %s/%s/%s/%s)." % (
                        msgno, forum, forumtitle,
                        unicode(message.date, 'cp850'),
                        unicode(message.time, 'cp850'),
                        unicode(message.mfrom, 'cp850'),
                        unicode(message.mto, 'cp850'),
                        unicode(message.subject, 'cp850'))
                    db.insert('message',
                               id = msgno,
                               forumid = forum,
                               boardid = bbsid,
                               mdate = unicode(message.date, 'cp850'),
                               mtime = unicode(message.time, 'cp850'),
                               mfrom = unicode(message.mfrom, 'cp850'),
                               mto = unicode(message.mto, 'cp850'),
                               reference = message.reference,
                               subject = unicode(message.subject, 'cp850'),
                               body = unicode(message.body, 'cp850')
                               )
                else:
                    yield "Ignoring duplicate message %d in forum %d %s." % (msgno, forum, forumtitle)
        yield "Done."

class BoardIndex:
    """
    List available forums in a given BBS.
    """
    def GET(self, board):
        if not auth():
            unauthorized()
            web.header('Content-Type', 'text/html; charset=utf-8')
            return render.unauthorized()
        boardnames = db.select('board', locals(), where='id = $board')
        if not boardnames:
            return "Unknown board."
        boardname = boardnames[0].title
        forums = db.select('forum', locals(), where='boardid = $board', order='id')
        web.header('Content-Type', 'text/html; charset=utf-8')
        return render.forumlist(board, boardname, list(forums))

class ForumIndex:
    """
    List all messages in a given forum. Paginate.
    """
    def GET(self, board, forum):
        if not auth():
            unauthorized()
            web.header('Content-Type', 'text/html; charset=utf-8')
            return render.unauthorized()

        form = web.input(start=0, size=100, order='id')
        start = int(form.start)
        size = int(form.size)
        order = form.order
        forum = int(forum)
        boardnames = db.select('board', locals(), where='id = $board')
        if not boardnames:
            return "Unknown board."
        boardname = boardnames[0].title
        forumnames = db.select('forum', locals(), where='id = $forum AND boardid = $board')
        if not forumnames:
            return "Unknown forum."
        forumname = forumnames[0].title

        # TODO: No pagination yet. Surely there is an elegant way to do this?
        mcount = db.select('message', locals(),
                            where='boardid = $board AND forumid = $forum',
                            what='count(*) as count')[0].count
        messages = db.select('message', locals(),
                              where='boardid = $board AND forumid = $forum',
                              what='id, mdate, mtime, mfrom, mto, subject',
                              offset='$start',
                              limit='$size',
                              order=order)
        if start == 0:
            prevstart = None
        else:
            prevstart = max(0, start-size)
        if start+size < mcount:
            nextstart = start+size
        else:
            nextstart = None

        web.header('Content-Type', 'text/html; charset=utf-8')
        return render.messagelist(board, boardname, forum, forumname, list(messages),
                                 order, size, prevstart=prevstart, nextstart=nextstart)

class ViewMessage:
    """
    View a message from a given board and forum.
    """
    def GET(self, board, forum, msgno):
        if not auth():
            unauthorized()
            web.header('Content-Type', 'text/html; charset=utf-8')
            return render.unauthorized()
        forum = int(forum)
        msgno = int(msgno)
        boardnames = db.select('board', locals(), where='id = $board')
        if not boardnames:
            return "Unknown board."
        boardname = boardnames[0].title
        forumnames = db.select('forum', locals(), where='id = $forum AND boardid = $board')
        if not forumnames:
            return "Unknown forum."
        forumname = forumnames[0].title
        # Retrieve and display message.
        messages = list(db.select('message', locals(),
                       where='id = $msgno AND forumid = $forum AND boardid = $board'))
        if len(messages) != 1:
            return "No such message."
        message = messages[0]
        if not message.reference:
            reference = None
        else:
            refno = message.reference
            references = list(db.select('message', locals(),
                        where='id = $refno AND forumid = $forum AND boardid = $board'))
            if len(references) > 0:
                reference = references[0]
            else:
                reference = None
        followups = list(db.select('message', locals(),
                        where='reference = $msgno AND forumid = $forum AND boardid = $board'))
        prevmsgs = list(db.select('message', locals(),
                        what='id, mfrom, mto, subject',
                        where='boardid = $board AND forumid = $forum AND id < $msgno',
                        order='id DESC', limit=1))
        if prevmsgs:
            prevmsg = prevmsgs[0]
        else:
            prevmsg = None
        nextmsgs = list(db.select('message', locals(),
                        what='id, mfrom, mto, subject',
                        where='boardid = $board AND forumid = $forum AND id > $msgno',
                        order='id ASC', limit=1))
        if nextmsgs:
            nextmsg = nextmsgs[0]
        else:
            nextmsg = None
        web.header('Content-Type', 'text/html; charset=utf-8')
        return render.message(board, boardname, forum, forumname, message, reference, followups,
                             prevmsg, nextmsg)


web.webapi.internalerror = web.debugerror
app = web.application(urls, globals())
application = app.wsgifunc()

if __name__ == '__main__':
    app.run()
