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


# A quick hack. Talk to the SMTP port.
# Right now this isn't very functional.
# A lot of functionality was borrowed directly from ftplib...
# John Viega (viega@list.org)

# >>> from smtplib import *
# >>> s = SmtpConnection('list.org')
# >>> s.helo('adder.cs.virginia.edu')
# >>> s.send(to='viega@list.org', frm='jtv2j@cs.virginia.edu', text='hello, world!')
# >>> s.quit()

from socket import *
import string, types

## DEBUG ...
#import sys
#from Mailman.Logging.StampedLogger import StampedLogger
#sys.error = StampedLogger("debug", label = 'smtplib', manual_reprime=1)
#sys.error.write("smtplib got debug\n")
## ... DEBUG

SMTP_PORT = 25

CRLF = '\r\n'

# Exception raised when an error or invalid response is received
error_reply = 'smtplib.error_reply'	# unexpected [123]xx reply
error_temp = 'smtplib.error_temp'	# 4xx errors
error_perm = 'smtplib.error_perm'	# 5xx errors
error_proto = 'smtplib.error_proto'	# response does not begin with [1-5]

class SmtpConnection:
    def __init__(self, host=''):
	self.host = host
	self._file = None
	self.connect()

    def connect(self):
	self._sock = socket(AF_INET, SOCK_STREAM)
	self._sock.connect(self.host, SMTP_PORT)
	self._file = self._sock.makefile('r')
	self.getresp()

    def helo(self, host):
	self._sock.send('HELO %s\r\n' % host)
	self.getresp()

    def quit(self):
	self._sock.send('QUIT\r\n')
	self.getresp()

    # text should be \n at eol, we'll add the \r.
    def send(self, to, frm, text, headers=None):
	if headers:
	    hlines = string.split(headers, '\n')
	lines  = string.split(text, '\n')
	self._sock.send('MAIL FROM: <%s>\r\n' % frm)
	self.getresp()
        if type(to) == types.StringType:
            self._sock.send('RCPT TO: <%s>\r\n' % to)
            self.getresp()
        else:
            for item in to:
                self._sock.send('RCPT TO: <%s>\r\n' % item)
                self.getresp(impunity=1)
	self._sock.send('DATA\r\n')
	self.getresp()
	if headers:
	    for line in hlines:
		self._sock.send(line + '\r\n')
	    self._sock.send('\r\n')
	for line in lines:
	    if line == '.': line = '..'
	    self._sock.send(line + '\r\n')
	self._sock.send('.\r\n')
	self.getresp()

# Private crap from here down.
    def getline(self):
	line = self._file.readline()
	if not line: raise EOFError
	if line[-2:] == CRLF: line = line[:-2]
	elif line[-1:] in CRLF: line = line[:-1]
	return line

    # Internal: get a response from the server, which may possibly
    # consist of multiple lines.  Return a single string with no
    # trailing CRLF.  If the response consists of multiple lines,
    # these are separated by '\n' characters in the string
    def getmultiline(self):
	line = self.getline()
	if line[3:4] == '-':
	    code = line[:3]
	    while 1:
		nextline = self.getline()
		line = line + ('\n' + nextline)
		if nextline[:3] == code and \
		   nextline[3:4] <> '-':
		    break
	return line

    def getresp(self, impunity=0):
	resp = self.getmultiline()
        if impunity:
            return resp
	self.lastresp = resp[:3]
	c = resp[:1]
	if c == '4':
	    raise error_temp, resp
	if c == '5':
	    raise error_perm, resp
	if c not in '123':
	    raise error_proto, resp
	return resp
