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

"""Produce and process the pending-approval items for a list."""

import sys
import os, cgi, string, types
from Mailman import Utils, MailList, Errors, htmlformat

def main():
    global list

    doc = htmlformat.Document()

    path = os.environ['PATH_INFO']
    list_info = Utils.GetPathPieces(path)


    if len(list_info) < 1:
        doc.SetTitle("Admindb Error")
        doc.AddItem(htmlformat.Header(2, "Invalid options to CGI script."))
        print doc.Format(bgcolor="#ffffff")
        sys.exit(0)
    list_name = string.lower(list_info[0])

    try:
      list = MailList.MailList(list_name)
    except:
      msg = "%s: No such list." % list_name
      doc.SetTitle("Admindb Error - %s" % msg)
      doc.AddItem(htmlformat.Header(2, msg))
      print doc.Format(bgcolor="#ffffff")
      sys.exit(0)

    if not list._ready:
        msg = "%s: No such list." % list_name
        doc.SetTitle("Admindb Error - %s" % msg)
        doc.AddItem(htmlformat.Header(2, msg))
        print doc.Format(bgcolor="#ffffff")
        sys.exit(0)

    try:
        form = cgi.FieldStorage()
        if len(form.keys()):
            doc.SetTitle("%s Admindb Results" % list.real_name)
            HandleRequests(doc)
        else:
            doc.SetTitle("%s Admindb" % list.real_name)
        PrintRequests(doc)
        text = doc.Format(bgcolor="#ffffff")
        print text
        sys.stdout.flush()
    finally:
        list.Unlock()



# Note, these 2 functions use i only to count the number of times to
# go around.  We always operate on the first element of the list
# because we're going to delete the element after we operate on it.

def SubscribeAll():
    for i in range(len(list.requests['add_member'])):
	comment_key = 'comment-%d' % list.requests['add_member'][0][0]
	if form.has_key(comment_key):
	    list.HandleRequest(('add_member', 0), 1, form[comment_key].value)
	else:
	    list.HandleRequest(('add_member', 0), 1)

def SubscribeNone():
    for i in range(len(list.requests['add_member'])):
	comment_key = 'comment-%d' % list.requests['add_member'][0][0]
	if form.has_key(comment_key):
	    list.HandleRequest(('add_member', 0), 0, form[comment_key].value)
	else:
	    list.HandleRequest(('add_member', 0), 0)

def PrintHeader(str, error=0):
    if error:
	it = htmlformat.FontAttr(str, color="ff5060")
    else:
	it = str
    doc.AddItem(htmlformat.Header(3, htmlformat.Italic(it)))
    doc.AddItem('<hr>')

def HandleRequests(doc):
    if not form.has_key('adminpw'):
	PrintHeader('You need to supply the admin password '
		    'to answer requests.', error=1)
	return
    try:
	list.ConfirmAdminPassword(form['adminpw'].value)
    except:
	PrintHeader('Incorrect admin password.', error=1)
	return
    ignore_subscribes = 0
    if form.has_key('subscribe_all'):
	ignore_subscribes = 1
	SubscribeAll()
    elif form.has_key('subscribe_none'):
	ignore_subscribes = 1
	SubscribeNone()
    for k in form.keys():
	try:
	    # XXX Security?!
	    v = eval(form[k].value)
	    request_id = eval(k)
	except: # For stuff like adminpw
	    continue
	if type(request_id) <> types.IntType:
	    continue
	try:
	    request = list.GetRequest(request_id)
	except Errors.MMBadRequestId:
	    continue # You've already changed the database.  No biggie.
	if ignore_subscribes and request[0] == 'add_member':
	    # We already handled this request.
	    continue
	comment_key = 'comment-%d' % request_id
	if form.has_key(comment_key):
	    list.HandleRequest(request, v, form[comment_key].value)
	else:
	    list.HandleRequest(request, v)
    list.Save()
    PrintHeader('Database Updated...')


def PrintAddMemberRequest(val, table):
    table.AddRow([
	val[3], 
	htmlformat.RadioButtonArray(val[0], ("Refuse", "Subscribe")),
	htmlformat.TextBox("comment-%d" % val[0], size=50)
	])

def PrintPostRequest(val, form):
    t = htmlformat.Table(cellspacing=10)
    t.AddRow([
	htmlformat.FontSize("+1",
			    htmlformat.Bold('Post held because: ')),
	val[3]])
    t.AddRow([
	htmlformat.FontSize("+1", 
			    htmlformat.Bold('Action to take on this post:')),
	htmlformat.RadioButtonArray(val[0], ("Approve", "Reject",
                                             "Discard (eg, spam)")),
	htmlformat.SubmitButton('submit', 'Submit All Data')
       ])
    t.AddRow([
	htmlformat.FontSize("+1", 
			    htmlformat.Bold('If you reject this post, '
					    'explain (optional):')),
	htmlformat.TextBox("comment-%d" % val[0], size=50)])

    cur_row = t.GetCurrentRowIndex()
    cur_col = t.GetCurrentCellIndex()
    t.AddCellInfo(cur_row, cur_col, colspan=3)

    t.AddRow([
	htmlformat.FontSize("+1", 
			    htmlformat.Bold('Contents:'))])
    form.AddItem(t)
    form.AddItem(htmlformat.Preformatted(val[2][1]))
    form.AddItem('<p>')



def PrintRequests(doc):
    # XXX: blech, yuk, ick
    global list

    # The only types of requests we know about are add_member and post.
    # Anything else that might have gotten in here somehow we'll just
    # ignore (This should never happen unless someone is hacking at
    # the code).

    doc.AddItem(htmlformat.Header(2, "Administrative requests for "
				  "'%s' mailing list" % list.real_name))
    doc.AddItem(htmlformat.FontSize("+1", htmlformat.Link(
	list.GetRelativeScriptURL('admin'), htmlformat.Italic(
	    'View or edit the list configuration information'))))
    doc.AddItem('<p><hr>')
    if not list.RequestsPending():
	doc.AddItem(htmlformat.Header(3,'There are no pending requests.'))
	doc.AddItem(list.GetMailmanFooter())
	return
    form = htmlformat.Form(list.GetRelativeScriptURL('admindb'))
    doc.AddItem(form)
    form.AddItem('Admin password: ')
    form.AddItem(htmlformat.PasswordBox('adminpw'))
    form.AddItem('<p>')
    if list.requests.has_key('add_member'):
##	form.AddItem('<hr>')
## 	t = htmlformat.Table(cellspacing=10)
## 	t.AddRow([
## 	    htmlformat.SubmitButton('submit', 'Submit All Data'),
## 	    htmlformat.SubmitButton('subscribe_all', 'Subscribe Everybody'),
## 	    htmlformat.SubmitButton('subscribe_none', 'Refuse Everybody')
## 	    ])
## 	form.AddItem(t)
	form.AddItem('<hr>')
	form.AddItem(htmlformat.Center(
	    htmlformat.Header(2, 'Subscription Requests')))
	t = htmlformat.Table(border=2)
	t.AddRow([
	    htmlformat.Bold('Email'),
	    htmlformat.Bold('Descision'),
	    htmlformat.Bold('Reasoning for subscription refusal (optional)')])
	for request in list.requests['add_member']:
	    PrintAddMemberRequest(request, t)

	form.AddItem(t)
	t = htmlformat.Table(cellspacing=10)
	t.AddRow([
	    htmlformat.SubmitButton('submit', 'Submit All Data'),
	    htmlformat.SubmitButton('subscribe_all', 'Subscribe Everybody'),
	    htmlformat.SubmitButton('subscribe_none', 'Refuse Everybody')
	    ])
	form.AddItem(t)

	# Print submitit buttons...
    if list.requests.has_key('post'):
	for request in list.requests['post']:
	    form.AddItem('<hr>')
	    form.AddItem(htmlformat.Center(htmlformat.Header(2, "Held Message")))
	    PrintPostRequest(request, form)
    doc.AddItem(list.GetMailmanFooter())

