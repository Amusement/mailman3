#! /usr/bin/env python
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

"""Produce listinfo page, primary web entry-point to mailing lists.
"""

# No lock needed in this script, because we don't change data.

import sys
import os, string
from regsub import gsub
from Mailman import Utils, MailList
from Mailman import mm_cfg
from Mailman.htmlformat import *

def main():
    try:
        path = os.environ['PATH_INFO']
    except KeyError:
        path = ""

    list_info = Utils.GetPathPieces(path)

    if len(list_info) == 0:
        FormatListinfoOverview()
        return

    list_name = string.lower(list_info[0])

    try:
        list = MailList.MailList(list_name, lock=0)
    except:
        list = None

    if not (list and list._ready):
        FormatListinfoOverview(error="List <em>%s</em> not found." % list_name)
        return

    FormatListListinfo(list)



def FormatListinfoOverview(error=None):
    "Present a general welcome and itemize the (public) lists for this host."
    doc = Document()
    legend = "%s mailing lists" % mm_cfg.DEFAULT_HOST_NAME
    doc.SetTitle(legend)

    table = Table(border=0, width="100%")
    table.AddRow([Center(Header(2, legend))])
    table.AddCellInfo(max(table.GetCurrentRowIndex(), 0), 0,
                      colspan=2, bgcolor="#99ccff")

    advertised = []
    names = Utils.list_names()
    names.sort()

    # XXX We need a portable way to determine the host by which we are being 
    #     visited!  An absolute URL would do...
    if os.environ.has_key('HTTP_HOST'):
	http_host = os.environ['HTTP_HOST']
    else:
	http_host = None

    for n in names:
	l = MailList.MailList(n, lock = 0)
	if l.advertised:
	    if (mm_cfg.VIRTUAL_HOST_OVERVIEW
                and http_host
		and (string.find(http_host, l.web_page_url) == -1
		     and string.find(l.web_page_url, http_host) == -1)):
		# List is for different identity of this host - skip it.
		continue
	    else:
		advertised.append(l)

    if error:
	greeting = FontAttr(error, color="ff5060", size="+1")
    else:
	greeting = "Welcome!"

    if not advertised:
        welcome_items = (greeting,
			 "<p>"
			 " There currently are no publicly-advertised ",
			 Link(mm_cfg.MAILMAN_URL, "mailman"),
			 " mailing lists on %s." % mm_cfg.DEFAULT_HOST_NAME,
			 )
    else:

        welcome_items = (
	    greeting,
            "<p>"
            " Below is the collection of publicly-advertised ",
            Link(mm_cfg.MAILMAN_URL, "mailman"),
            " mailing lists on %s." % mm_cfg.DEFAULT_HOST_NAME,
            (' Click on a list name to visit the info page'
             ' for that list.  There you can learn more about the list,'
             ' subscribe to it, or find the roster of current subscribers.'),
            )

    welcome_items = (welcome_items +
                     (" To visit the info page for an unadvertised list,"
                      " open a URL similar to this one, but with a '/' and"
                      +
                      (" the %slist name appended."
                       % ((error and "right ") or ""))
                      +
                      '<p> List administrators, you can visit ',
                      Link("%sadmin/" % ('../' * Utils.GetNestingLevel()),
                           "the list admin overview page"),
                      " to find the management interface for your list."
                      "<p>(Send questions or comments to ",
                      Link("mailto:%s" % mm_cfg.MAILMAN_OWNER,
                           mm_cfg.MAILMAN_OWNER),
                      ".)<p>"))

    table.AddRow([apply(Container, welcome_items)])
    table.AddCellInfo(max(table.GetCurrentRowIndex(), 0), 0, colspan=2)

    if advertised:
        table.AddRow([Italic("List"), Italic("Description")])
    for l in advertised:
        table.AddRow([Link(l.GetRelativeScriptURL('listinfo'), 
	      Bold(l.real_name)), l.description])

    doc.AddItem(table)

    print doc.Format(bgcolor="#ffffff")

def FormatListListinfo(list):
    "Expand the listinfo template against the list's settings, and print."

    doc = HeadlessDocument()

    replacements = list.GetStandardReplacements()

    if not list.digestable or not list.nondigestable:
        replacements['<mm-digest-radio-button>'] = ""
        replacements['<mm-undigest-radio-button>'] = ""
    else:
        replacements['<mm-digest-radio-button>'] = list.FormatDigestButton()
        replacements['<mm-undigest-radio-button>'] = \
                                                   list.FormatUndigestButton()
    replacements['<mm-plain-digests-button>'] = list.FormatPlainDigestsButton()
    replacements['<mm-mime-digests-button>'] = list.FormatMimeDigestsButton()
    replacements['<mm-subscribe-box>'] = list.FormatBox('email')
    replacements['<mm-subscribe-button>'] = list.FormatButton('email-button',
                                                              text='Subscribe')
    replacements['<mm-new-password-box>'] = list.FormatSecureBox('pw')
    replacements['<mm-confirm-password>'] = list.FormatSecureBox('pw-conf')
    replacements['<mm-subscribe-form-start>'] = \
                                              list.FormatFormStart('subscribe')
    replacements['<mm-roster-form-start>'] = list.FormatFormStart('roster')
    replacements['<mm-editing-options>'] = list.FormatEditingOption()
    replacements['<mm-info-button>'] = SubmitButton('UserOptions',
                                                    'Edit Options').Format()
    replacements['<mm-roster-option>'] = list.FormatRosterOptionForUser()

    # Do the expansion.
    doc.AddItem(list.ParseTags('listinfo.html', replacements))

    print doc.Format()


if __name__ == "__main__":
    main()
