# Copyright (C) 1998,1999,2000 by the Free Software Foundation, Inc.
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

"""Produce subscriber roster, using listinfo form data, roster.html template.

Takes listname in PATH_INFO.
"""


# We don't need to lock in this script, because we're never going to change
# data. 

import sys
import os, string
import cgi
from Mailman import Utils, MailList, htmlformat, Errors

def main():
    doc = htmlformat.HeadlessDocument()
    form = cgi.FieldStorage()
    list = get_list()

    bad = ""
    # These nested conditionals constituted a cascading authentication
    # check, yielding a 
    if not list.private_roster:
        # No privacy.
        bad = ""
    else:
        auth_req = ("%s subscriber list requires authentication."
                    % list.real_name)
        if not form.has_key("roster-pw"):
            bad = auth_req
        else:
            pw = form['roster-pw'].value
            # Just the admin password is sufficient - check it early.
            if not list.ValidAdminPassword(pw):
                if not form.has_key('roster-email'):
                    # No admin password and no user id, nogo.
                    bad = auth_req
                else:
                    id = form['roster-email'].value
                    if list.private_roster == 1:
                        # Private list - members visible.
                        try:
                            list.ConfirmUserPassword(id, pw)
                        except (Errors.MMBadUserError, 
                                Errors.MMBadPasswordError,
                                Errors.MMNotAMemberError):
                            bad = ("%s subscriber authentication failed."
                                   % list.real_name)
                    else:
                        # Anonymous list - admin-only visible
                        # - and we already tried admin password, above.
                        bad = ("%s admin authentication failed."
                               % list.real_name)
    if bad:
        doc = error_page_doc(bad)
        doc.AddItem(list.GetMailmanFooter())
        print doc.Format()
        sys.exit(0)

    replacements = list.GetAllReplacements()
    doc.AddItem(list.ParseTags('roster.html', replacements))
    print doc.Format()

def get_list():
    "Return list or bail out with error page."
    list_info = []
    try:
        list_info = Utils.GetPathPieces(os.environ['PATH_INFO'])
    except KeyError:
        pass
    if len(list_info) != 1:
        error_page("Invalid options to CGI script.")
        sys.exit(0)
    listname = string.lower(list_info[0])
    try:
        mlist = MailList.MailList(listname, lock=0)
        mlist.IsListInitialized()
    except Errors.MMListError, e:
        error_page('No such list <em>%s</em>' % listname)
        sys.stderr.write('No such list "%s": %s\n' % (listname, e))
        sys.exit(0)
    return mlist


def error_page(errmsg, *args):
    print apply(error_page_doc, (errmsg,) + args).Format()


def error_page_doc(errmsg, *args):
    """Produce a simple error-message page on stdout and exit.

    Optional arg justreturn means just return the doc, don't print it."""
    doc = htmlformat.Document()
    doc.SetTitle("Error")
    doc.AddItem(htmlformat.Header(2, "Error"))
    doc.AddItem(htmlformat.Bold(errmsg % args))
    return doc







