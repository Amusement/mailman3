# Copyright (C) 1998 by the Free Software Foundation, Inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software 
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

"""Parse bounce messages generated by Postfix."""


import string
import re
import multifile
import mimetools

from Mailman.pythonlib.StringIO import StringIO



def process(mlist, msg):
    if msg.gettype() <> 'multipart/mixed':
        return None
    boundary = msg.getparam('boundary')
    msg.fp.seek(0)
    mfile = multifile.MultiFile(msg.fp)
    mfile.push(boundary)
    # find the subpart with message/delivery-status information
    while 1:
        try:
            more = mfile.next()
        except multifile.Error:
            # looked like a multipart, but really wasn't
            return None
        if not more:
            # we didn't find it
            return None
        s = StringIO(mfile.read())
        msg2 = mimetools.Message(s)
        if msg2.gettype() == 'text/plain':
            desc = msg2.get('content-description')
            if desc and string.lower(desc) == 'notification':
                return findaddr(msg2.fp)
            # probably not a Postfix bounce
            return None



# are these heuristics correct or guaranteed?
pcre = re.compile(r'\t\t\tthe postfix program$', re.IGNORECASE)
acre = re.compile(r'<(?P<addr>[^>]*)>:')

def findaddr(fp):
    addrs = []
    # simple state machine
    #     0 == nothing found
    #     1 == salutation found
    state = 0
    while 1:
        line = fp.readline()
        if not line:
            break
        # preserve leading whitespace
        line = string.rstrip(line)
        # yes use match to match at beginning of string
        if state == 0 and pcre.match(line):
            state = 1
        elif state == 1 and line:
            mo = acre.search(line)
            if mo:
                addrs.append(mo.group('addr'))
            # probably a continuation line
    return addrs or None
