#! /usr/bin/env python -u
#
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

"""Provide a password-interface wrapper around private archives.

Currently this is organized to obtain passwords for Mailman mailing list
subscribers.
"""

import sys, os, string
from Mailman import MailList, Errors
from Mailman import Cookie
from Mailman.Logging.Utils import LogStdErr
from Mailman import Utils
import Mailman.mm_cfg

LogStdErr("error", "private")


PAGE = '''
<html>
<head>
  <title>%(listname)s Private Archives Authentication</title>
</head>
<body bgcolor="#ffffff">
<FORM METHOD=POST ACTION="%(basepath)s/">
  <TABLE WIDTH="100%%" BORDER="0" CELLSPACING="4" CELLPADDING="5">
    <TR>
      <TD COLSPAN="2" WIDTH="100%%" BGCOLOR="#99CCFF" ALIGN="CENTER">
	<B><FONT COLOR="#000000" SIZE="+1">%(listname)s Private Archives
	    Authentication</FONT></B>
      </TD>
    </TR>
    <tr>
      <td COLSPAN="2"> <P>%(message)s </td>
    <tr>
    </tr>
      <TD> <div ALIGN="Right">Address:  </div></TD>
      <TD> <INPUT TYPE=TEXT NAME=username SIZE=30> </TD>
    <tr>
    </tr>
      <TD> <div ALIGN="Right"> Password: </div> </TD>
      <TD> <INPUT TYPE=password NAME=password SIZE=30></TD>
    <tr>
    </tr>
      <td></td>
      <td> <INPUT TYPE=SUBMIT>
      </td>
    </tr>
  </TABLE>
</FORM>
'''

	
login_attempted = 0
_list = None

def GetListobj(list_name):
    """Return an unlocked instance of the named mailing list, if found."""
    global _list
    if _list:
	return _list
    _list = MailList.MailList(list_name, lock=0)
    return _list

def isAuthenticated(list_name):
    try:
        listobj = GetListobj(list_name)
    except Errors.MMUnknownListError:
        print "\n<H3>List", repr(list_name), "not found.</h3>"
        raise SystemExit
    if os.environ.has_key('HTTP_COOKIE'):
	c = Cookie.Cookie( os.environ['HTTP_COOKIE'] )
	if c.has_key(list_name):
            if listobj.CheckCookie(c[list_name].value):
                return 1
    # No corresponding cookie.  OK, then check for username, password
    # CGI variables 
    import cgi
    v = cgi.FieldStorage()
    username = password = None
    if v.has_key('username'): 
	username = v['username']
	if type(username) == type([]): username = username[0]
	username = username.value
    if v.has_key('password'): 
	password = v['password']
	if type(password) == type([]): password = password[0]
	password = password.value
	
    if username is None or password is None: return 0

    # Record that this is a login attempt, so if it fails the form can
    # be displayed with an appropriate message.
    global login_attempted
    login_attempted=1
    try:
	listobj.ConfirmUserPassword( username, password)
    except (Errors.MMBadUserError, Errors.MMBadPasswordError,
            Errors.MMNotAMemberError): 
	return 0

    token = listobj.MakeCookie()
    c = Cookie.Cookie()
    c[list_name] = token
    print c				# Output the cookie
    return 1


def true_path(path):
    "Ensure that the path is safe by removing .."
    path = string.replace(path, "../", "")
    path = string.replace(path, "./", "")
    return path[1:]


def content_type(path):
    if path[-3:] == '.gz':
        path = path[:-3]
    if path[-4:] == '.txt':
        return 'text/plain'
    return 'text/html'


def main():
    path = os.environ.get('PATH_INFO', "/index.html")
    true_filename = os.path.join(
        Mailman.mm_cfg.PRIVATE_ARCHIVE_FILE_DIR,
        true_path(path))
    list_info = Utils.GetPathPieces(path)
    if len(list_info) == 0:
        list_name = None
    else:
        list_name = string.lower(list_info[0])

    # If it's a directory, we have to append index.html in this script.  We
    # must also check for a gzipped file, because the text archives are
    # usually stored in compressed form.
    if os.path.isdir(true_filename):
        true_filename = true_filename + '/index.html'
    if not os.path.exists(true_filename) and \
       os.path.exists(true_filename + '.gz'):
        # then
        true_filename = true_filename + '.gz'

    if not list_name or not isAuthenticated(list_name):
        # Output the password form
        print 'Content-type: text/html\n'
        page = PAGE

        if not list_name:
            print '\n<h3>No list name found.</h3>'
            raise SystemExit
        try:
            listobj = GetListobj(list_name)
        except Errors.MMUnknownListError:
            print "\n<H3>List", repr(list_name), "not found.</h3>"
            raise SystemExit
        if login_attempted:
            message = ("Your email address or password were incorrect."
                       " Please try again.")
        else:
            message = ("Please enter your %s subscription email address"
                       " and password." % listobj.real_name)
        while path and path[0] == '/': path=path[1:]  # Remove leading /'s
        basepath = os.path.split(listobj.GetBaseArchiveURL())[0]
        listname = listobj.real_name
        print '\n\n', page % vars()
        sys.exit(0)

    # Authorization confirmed... output the desired file
    try:
        if true_filename[-3:] == '.gz':
            import gzip
            f = gzip.open(true_filename, 'r')
        else:
            f = open(true_filename, 'r')
    except IOError:
        print 'Content-type: text/html\n'

        print "<H3>Archive File Not Found</H3>"
        print "No file", path, '(%s)' % true_filename
    else:
        print 'Content-type:', content_type(path), '\n'
        while (1):
            data = f.read(16384)
            if data == "": break
            sys.stdout.write(data)
        f.close()
