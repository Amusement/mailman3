# Copyright (C) 1998,1999,2000,2001 by the Free Software Foundation, Inc.
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

import os
import types
import cgi
from errno import ENOENT

from mimelib.Parser import Parser

from Mailman import mm_cfg
from Mailman import Utils
from Mailman import MailList
from Mailman import Errors
from Mailman import Message
from Mailman.Cgi import Auth
from Mailman.htmlformat import *
from Mailman.Logging.Syslog import syslog
from Mailman.i18n import _

NL = '\n'



def handle_no_list(doc, extra=''):
    doc.SetTitle(_('Mailman Admindb Error'))
    doc.AddItem(Header(2, _('Mailman Admindb Error')))
    doc.AddItem(extra)
    doc.AddItem(_('You must specify a list name.  Here is the '))
    link = mm_cfg.DEFAULT_URL
    if link[-1] <> '/':
        link = link + '/'
    link = link + 'admin'
    doc.AddItem(Link(link, _('list of available mailing lists.')))
    print doc.Format(bgcolor="#ffffff")



def main():
    doc = Document()
    # figure out which list we're going to process
    parts = Utils.GetPathPieces()
    if not parts:
        handle_no_list(doc)
        return
    # get URL components.  the list name should be the zeroth part
    try:
        listname = parts[0].lower()
    except IndexError:
        handle_no_list(doc)
        return
    # now that we have the list name, create the list object
    try:
        mlist = MailList.MailList(listname)
    except Errors.MMListError, e:
        handle_no_list(doc, _('No such list <em>%(listname)s</em><p>'))
        syslog('error', 'No such list "%s": %s\n' % (listname, e))
        return

    os.environ['LANG'] = mlist.preferred_language

    #
    # now we must authorize the user to view this page, and if they are, to
    # handle both the printing of the current outstanding requests, and the
    # selected actions
    try:
        cgidata = cgi.FieldStorage()
        try:
            Auth.authenticate(mlist, cgidata)
        except Auth.NotLoggedInError, e:
            Auth.loginpage(mlist, 'admindb', e.message)
            return

        # If this is a form submission, then we'll process the requests and
        # print the results.  otherwise (there are no keys in the form), we'll
        # print out the list of pending requests
        #
        realname = mlist.real_name
        if len(cgidata.keys()):
            doc.SetTitle(_("%(realname)s Admindb Results"))
            HandleRequests(mlist, doc, cgidata)
        else:
            doc.SetTitle(_("%(realname)s Admindb"))
        PrintRequests(mlist, doc)
        text = doc.Format(bgcolor="#ffffff")
        print text
    finally:
        mlist.Save()
        mlist.Unlock()



def PrintRequests(mlist, doc):
    # The only types of requests we know about are add member and post.
    # Anything else that might have gotten in here somehow we'll just ignore
    # (This should never happen unless someone is hacking at the code).
    doc.AddItem(Header(2, _('Administrative requests for mailing list:') + ' <em>' +
                       mlist.real_name + '</em>'))
    # short circuit for when there are no pending requests
    if not mlist.NumRequestsPending():
        doc.AddItem(_('There are no pending requests.'))
        doc.AddItem(mlist.GetMailmanFooter())
        return

    doc.AddItem(Utils.maketext(
        'admindbpreamble.html', {'listname': mlist.real_name},
        lang=mlist.preferred_language, raw=1))
    doc.AddItem('.<p>')
    form = Form(mlist.GetScriptURL('admindb'))
    doc.AddItem(form)
    form.AddItem(SubmitButton('submit', _('Submit All Data')))
    #
    # Add the subscription request section
    subpendings = mlist.GetSubscriptionIds()
    if subpendings:
        form.AddItem('<hr>')
        form.AddItem(Center(Header(2, _('Subscription Requests'))))
        t = Table(border=2)
        t.AddRow([
            Bold(_('Address')),
            Bold(_('Your Decision')),
            Bold(_('If you refuse this subscription, please explain (optional)'))
            ])
        for id in subpendings:
            PrintAddMemberRequest(mlist, id, t)
        form.AddItem(t)
    # Post holds are now handled differently
    heldmsgs = mlist.GetHeldMessageIds()
    total = len(heldmsgs)
    if total:
        count = 1
        for id in heldmsgs:
            info = mlist.GetRecord(id)
            PrintPostRequest(mlist, id, info, total, count, form)
            count = count + 1
    form.AddItem('<hr>')
    form.AddItem(SubmitButton('submit', _('Submit All Data')))
    doc.AddItem(mlist.GetMailmanFooter())



def PrintAddMemberRequest(mlist, id, table):
    time, addr, passwd, digest, lang  = mlist.GetRecord(id)
    table.AddRow([addr,
                  RadioButtonArray(id, (_('Subscribe'), _('Refuse')),
                                   values=(mm_cfg.SUBSCRIBE, mm_cfg.REJECT)),
                  TextBox('comment-%d' % id, size=60)
                  ])



def PrintPostRequest(mlist, id, info, total, count, form):
    # For backwards compatibility with pre 2.0beta3
    if len(info) == 5:
        ptime, sender, subject, reason, filename = info
        msgdata = {}
    else:
        ptime, sender, subject, reason, filename, msgdata = info
    form.AddItem('<hr>')
    msg = _('Posting Held for Approval')
    if total <> 1:
        msg = msg + _(' (%d of %d)') % (count, total)
    form.AddItem(Center(Header(2, msg)))
    p = Parser(Message.Message)
    try:
        fp = open(os.path.join(mm_cfg.DATA_DIR, filename))
        msg = p.parse(fp)
        fp.close()
        text = msg.get_text()[:mm_cfg.ADMINDB_PAGE_TEXT_LIMIT]
    except IOError, (code, msg):
        if code == ENOENT:
            form.AddItem(_('<em>Message with id #%d was lost.') % id)
            form.AddItem('<p>')
            # TBD: kludge to remove id from requests.db.  value==2 means
            # discard the message.
            try:
                mlist.HandleRequest(id, mm_cfg.DISCARD)
            except Errors.LostHeldMessage:
                pass
            return
        raise
    t = Table(cellspacing=0, cellpadding=0, width='100%')
    t.AddRow([Bold(_('From:')), sender])
    row, col = t.GetCurrentRowIndex(), t.GetCurrentCellIndex()
    t.AddCellInfo(row, col-1, align='right')
    # HTML quote the subject so it doesn't mess up the page.  E.g. a message
    # with "Subject: </table>"
    quoted = subject.replace('<', '&lt;').replace('>', '&gt;')
    t.AddRow([Bold(_('Subject:')), quoted])
    t.AddCellInfo(row+1, col-1, align='right')
    t.AddRow([Bold(_('Reason:')), reason])
    t.AddCellInfo(row+2, col-1, align='right')
    # We can't use a RadioButtonArray here because horizontal placement can be
    # confusing to the user and vertical placement takes up too much
    # real-estate.  This is a hack!
    buttons = Table(cellspacing="5", cellpadding="0")
    buttons.AddRow(map(lambda x, s='&nbsp;'*5: s+x+s,
                       (_('Defer'), _('Approve'), _('Reject'), _('Discard'))))
    buttons.AddRow([Center(RadioButton(id, mm_cfg.DEFER, 1)),
                    Center(RadioButton(id, mm_cfg.APPROVE, 0)),
                    Center(RadioButton(id, mm_cfg.REJECT, 0)),
                    Center(RadioButton(id, mm_cfg.DISCARD, 0)),
                    ])
    t.AddRow([Bold(_('Action:')), buttons])
    t.AddCellInfo(row+3, col-1, align='right')
    t.AddRow(['&nbsp;',
              CheckBox('preserve-%d' % id, 'on', 0).Format() +
              '&nbsp;' + _('Preserve message for site administrator')
              ])
    t.AddRow(['&nbsp;',
              CheckBox('forward-%d' % id, 'on', 0).Format() +
              '&nbsp;' + _('Additionally, forward this message to: ') +
              TextBox('forward-addr-%d' % id, size=47,
                      value=mlist.GetOwnerEmail()).Format()
              ])
    t.AddRow([
        Bold(_('If you reject this post,<br>please explain (optional):')),
        TextArea('comment-%d' % id, rows=4, cols=80,
                 text = Utils.wrap(msgdata.get('rejection-notice',
                                               _('[No explanation given]')),
                                   column=80))
        ])
    row, col = t.GetCurrentRowIndex(), t.GetCurrentCellIndex()
    t.AddCellInfo(row, col-1, align='right')
    hdrtxt = NL.join(['%s: %s' % (k, v) for k, v in msg.items()])
    t.AddRow([Bold(_('Message Headers:')),
              TextArea('headers-%d' % id, hdrtxt,
                       rows=10, cols=80)])
    row, col = t.GetCurrentRowIndex(), t.GetCurrentCellIndex()
    t.AddCellInfo(row, col-1, align='right')
    t.AddRow    ([Bold(_('Message Excerpt:')),
              TextArea('fulltext-%d' % id, text, rows=10, cols=80)])
    t.AddCellInfo(row+1, col-1, align='right')
    form.AddItem(t)
    form.AddItem('<p>')



def HandleRequests(mlist, doc, cgidata):
    erroraddrs = []
    for k in cgidata.keys():
        formv = cgidata[k]
        if type(formv) == types.ListType:
            continue
        try:
            v = int(formv.value)
            request_id = int(k)
        except ValueError:
            continue
        # get the action comment and reasons if present
        commentkey = 'comment-%d' % request_id
        preservekey = 'preserve-%d' % request_id
        forwardkey = 'forward-%d' % request_id
        forwardaddrkey = 'forward-addr-%d' % request_id
        # defaults
        comment = _('[No reason given]')
        preserve = 0
        forward = 0
        forwardaddr = ''
        if cgidata.has_key(commentkey):
            comment = cgidata[commentkey].value
        if cgidata.has_key(preservekey):
            preserve = cgidata[preservekey].value
        if cgidata.has_key(forwardkey):
            forward = cgidata[forwardkey].value
        if cgidata.has_key(forwardaddrkey):
            forwardaddr = cgidata[forwardaddrkey].value
        #
        # handle the request id
        try:
            mlist.HandleRequest(request_id, v, comment,
                                preserve, forward, forwardaddr)
        except (KeyError, Errors.LostHeldMessage):
            # that's okay, it just means someone else has already updated the
            # database, so just ignore this id
            continue
        except Errors.MMAlreadyAMember, v:
            erroraddrs.append(v)
    # save the list and print the results
    mlist.Save()
    doc.AddItem(Header(2, _('Database Updated...')))
    if erroraddrs:
        for addr in erroraddrs:
            doc.AddItem(`addr` + _(' is already a member') + '<br>')
