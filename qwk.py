#!/usr/bin/env python
# QWK library.

"""
QWK library in Python. Only implements reading messages out of a Zip
compressed QWK packet.
"""

__version__='0.1'

import struct
from zipfile import ZipFile
from StringIO import StringIO

#MESSAGES.DAT record:
#Offset  Length  Description
#------  ------  ----------------------------------------------------
#    1       1   Message status flag (unsigned character)
#                ' ' = public, unread
#                '-' = public, read
#                '*' = private, read by someone but not by intended
#                      recipient
#                '+' = private, read by official recipient
#                '~' = comment to Sysop, unread
#                '`' = comment to Sysop, read
#                '%' = sender password protected, unread
#                '^' = sender password protected, read
#                '!' = group password protected, unread
#                '#' = group password protected, read
#                '$' = group password protected to all
#    2       7   Message number (in ASCII)
#    9       8   Date (mm-dd-yy, in ASCII)
#   17       5   Time (24 hour hh:mm, in ASCII)
#   22      25   To (uppercase, left justified)
#   47      25   From (uppercase, left justified)
#   72      25   Subject of message (mixed case)
#   97      12   Password (space filled)
#  109       8   Reference message number (in ASCII)
#  117       6   Number of 128-bytes blocks in message (including the
#                header, in ASCII; the lowest value should be 2, header
#                plus one block message; this number may not be left
#                flushed within the field)
#  123       1   Flag (ASCII 225 means message is active; ASCII 226
#                means this message is to be killed)
#  124       2   Conference number (unsigned word)
#  126       2   Logical message number in the current packet; i.e.
#                this number will be 1 for the first message, 2 for the
#                second, and so on. (unsigned word)
#  128       1   Indicates whether the message has a network tag-line
#                or not.  A value of '*' indicates that a network tag-
#                line is present; a value of ' ' (space) indicates
#                there isn't one.  Messages sent to readers (non-net-
#                status) generally leave this as a space.  Only network
#                softwares need this information.

class QwkMessage:
    """
    Contains the headers and body of a QWK message.
    """
    def __init__(self, status, number, date, time, mto, mfrom, subject,
        password, reference, forum, body):
        self.status = status
        self.number = number
        self.date = date
        self.time = time
        self.mto = mto
        self.mfrom = mfrom
        self.subject = subject
        self.password = password
        self.reference = reference
        self.forum = forum
        self.body = body
        if status in ['*', '+']:
            self.private = 1
        else:
            self.private = 0

class QwkPacket:
    """
    Opens and reads messages from a QWK packet.
    """

    # MESSAGES.DAT header record. See commented area above.
    record_layout = '<c7s8s5s25s25s25s12s8s6sxHxxx'

    def __init__(self, packet):
        """
        Creates a new QwkPacket instance. The packet parameter must
        be a file name or a file like object.
        """
        # Open packet
        zip = ZipFile(packet, 'r')
        # Read CONTROL.DAT
        cd = StringIO(zip.read('CONTROL.DAT'))
        controldat = cd.readlines()
        cd.close()
        # Read BBS id
        self.bbsname = controldat[0].strip()
        self.bbsid = controldat[4].split(',')[1].strip()
        # Read forum list
        self._readForums(controldat)
        # Read messages
        md = StringIO(zip.read('MESSAGES.DAT'))
        self._readMessages(md)
        # Wrap up
        md.close()
        zip.close()

    def _decodeHeader(self, data):
        headers = struct.unpack(self.record_layout, data)
        hd = {}
        hd['status'] = headers[0]
        hd['number'] = int(headers[1].strip() or 0)
        hd['date'] = headers[2].strip()
        hd['time'] = headers[3].strip()
        hd['to'] = headers[4].strip()
        hd['from'] = headers[5].strip()
        hd['subject']= headers[6].strip()
        hd['password'] = headers[7].strip()
        hd['reference'] = int(headers[8].strip() or 0)
        hd['blocks'] = int(headers[9].strip() or 0)
        hd['forum'] = headers[10]
        return hd

    def _readForums(self, controldat):
        """
        Read conference list out of the controldat file lines.
        """
        forums = {}
        count = int(controldat[10].strip())+1
        for x in range(11, 11+(count*2), 2):
            forums[int(controldat[x].strip())] = {'title':
                controldat[x+1].strip(), 'messages': []}
        self.forums = forums

    def _readMessages(self, file):
        """
        Reads messages out of a MESSAGES.DAT file. Parameter is a
        file like object.
        """
        messages = []
        file.seek(128, 0) # Skip the copyright header

        block = file.read(128)
        while block != '':
            headers = self._decodeHeader(block)
            body = ''
            for x in range(headers['blocks'] - 1):
                body = body + file.read(128)
            # Replace QWK's EOL characters with current standards.
            body = body.replace(chr(227), '\r\n')
            # Discard null bytes. For some reason strip() doesn't do it.
            body = body.replace(chr(0), '')

            message = QwkMessage(headers['status'], headers['number'],
                headers['date'], headers['time'], headers['to'],
                headers['from'], headers['subject'],
                headers['password'], headers['reference'],
                headers['forum'], body)
            messages.append(message)
            self.forums[headers['forum']]['messages'].append(message)

            # Loop all over again.
            block = file.read(128)
        self.messages = messages


if __name__=='__main__':
    # Testing here.

    import sys
    if len(sys.argv) < 2:
        print "Usage:"
        print "%s: bbsid.qwk ..."
    else:
        for filename in sys.argv[1:]:
            qwk = QwkPacket(filename)

            print "BBS:", qwk.bbsname
            print "BBS id:", qwk.bbsid
            print "Forums:", len(qwk.forums.keys())
            print "Messages:", len(qwk.messages)
            print "-"*80

            for message in qwk.messages:
                print "Date:", message.date, message.time
                print "From:", message.mfrom
                print "To:", message.mto
                print "Subject:", message.subject
                print "Forum:", qwk.forums[message.forum]['title']
                print "Number:", message.number
                print "Reference:", message.reference
                print
                print message.body
                print "-"*80
