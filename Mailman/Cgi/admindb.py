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

import sys
import os
import cgi
import errno
import signal
import email
from types import ListType
from urllib import quote_plus, unquote_plus

from Mailman import mm_cfg
from Mailman import Utils
from Mailman import MailList
from Mailman import Errors
from Mailman import Message
from Mailman import i18n
from Mailman.ListAdmin import readMessage
from Mailman.Cgi import Auth
from Mailman.htmlformat import *
from Mailman.Logging.Syslog import syslog

EMPTYSTRING = ''
NL = '\n'

# Set up i18n.  Until we know which list is being requested, we use the
# server's default.
_ = i18n._
i18n.set_language(mm_cfg.DEFAULT_SERVER_LANGUAGE)



def helds_by_sender(mlist):
    heldmsgs = mlist.GetHeldMessageIds()
    bysender = {}
    for id in heldmsgs:
        sender = mlist.GetRecord(id)[1]
        bysender.setdefault(sender, []).append(id)
    return bysender


def hacky_radio_buttons(btnname, labels, values, defaults, spacing=3):
    # We can't use a RadioButtonArray here because horizontal placement can be
    # confusing to the user and vertical placement takes up too much
    # real-estate.  This is a hack!
    space = '&nbsp;' * spacing
    btns = Table(cellspacing='5', cellpadding='0')
    btns.AddRow([space + text + space for text in labels])
    btns.AddRow([Center(RadioButton(btnname, value, default))
                 for value, default in zip(values, defaults)])
    return btns



def main():
    # Figure out which list is being requested
    parts = Utils.GetPathPieces()
    if not parts:
        handle_no_list()
        return

    listname = parts[0].lower()
    try:
        mlist = MailList.MailList(listname, lock=0)
    except Errors.MMListError, e:
        # Avoid cross-site scripting attacks
        safelistname = cgi.escape(listname)
        handle_no_list(_('No such list <em>%(safelistname)s</em>'))
        syslog('error', 'No such list "%s": %s\n', listname, e)
        return

    # Now that we know which list to use, set the system's language to it.
    i18n.set_language(mlist.preferred_language)

    # Make sure the user is authorized to see this page.
    cgidata = cgi.FieldStorage(keep_blank_values=1)

    if not mlist.WebAuthenticate((mm_cfg.AuthListAdmin,
                                  mm_cfg.AuthListModerator,
                                  mm_cfg.AuthSiteAdmin),
                                 cgidata.getvalue('adminpw', '')):
        if cgidata.has_key('adminpw'):
            # This is a re-authorization attempt
            msg = Bold(FontSize('+1', _('Authorization failed.'))).Format()
        else:
            msg = ''
        Auth.loginpage(mlist, 'admindb', msg=msg)
        return

    # Set up the results document
    doc = Document()
    doc.set_language(mlist.preferred_language)
    
    # See if we're requesting all the messages for a particular sender, or if
    # we want a specific held message.
    sender = None
    msgid = None
    details = None
    envar = os.environ.get('QUERY_STRING')
    if envar:
        # POST methods, even if their actions have a query string, don't get
        # put into FieldStorage's keys :-(
        qs = cgi.parse_qs(envar).get('sender')
        if qs and type(qs) == ListType:
            sender = qs[0]
        qs = cgi.parse_qs(envar).get('msgid')
        if qs and type(qs) == ListType:
            msgid = qs[0]
        qs = cgi.parse_qs(envar).get('details')
        if qs and type(qs) == ListType:
            details = qs[0]

    # We need a signal handler to catch the SIGTERM that can come from Apache
    # when the user hits the browser's STOP button.  See the comment in
    # admin.py for details.
    #
    # BAW: Strictly speaking, the list should not need to be locked just to
    # read the request database.  However the request database asserts that
    # the list is locked in order to load it and it's not worth complicating
    # that logic.
    def sigterm_handler(signum, frame, mlist=mlist):
        # Make sure the list gets unlocked...
        mlist.Unlock()
        # ...and ensure we exit, otherwise race conditions could cause us to
        # enter MailList.Save() while we're in the unlocked state, and that
        # could be bad!
        sys.exit(0)

    mlist.Lock()
    try:
        # Install the emergency shutdown signal handler
        signal.signal(signal.SIGTERM, sigterm_handler)

        realname = mlist.real_name
        if not cgidata.keys():
            # If this is not a form submission (i.e. there are no keys in the
            # form), then all we don't need to do much special.
            doc.SetTitle(_('%(realname)s Administrative Database'))
        elif not details:
            # This is a form submission
            doc.SetTitle(_('%(realname)s Administrative Database Results'))
            process_form(mlist, doc, cgidata)
        # Now print the results and we're done
        # Short circuit for when there are no pending requests
        if not mlist.NumRequestsPending():
            title = _('%(realname)s Administrative Database')
            doc.SetTitle(title)
            doc.AddItem(Header(2, title))
            doc.AddItem(_('There are no pending requests.'))
            doc.AddItem(mlist.GetMailmanFooter())
            print doc.Format()
            return

        admindburl = mlist.GetScriptURL('admindb', absolute=1)
        form = Form(admindburl)
        # Add the instructions template
        if details:
            doc.AddItem(Header(
                2, _('Detailed instructions for the administrative database')))
        else:
            doc.AddItem(Header(
                2,
                _('Administrative requests for mailing list:')
                + ' <em>%s</em>' % mlist.real_name))
        if not details:
            form.AddItem(Center(SubmitButton('submit', _('Submit All Data'))))
        # Add a link back to the overview, if we're not viewing the overview!
        adminurl = mlist.GetScriptURL('admin', absolute=1)
        d = {'listname'  : mlist.real_name,
             'detailsurl': admindburl + '?details=instructions',
             'summaryurl': admindburl,
             'viewallurl': admindburl + '?details=all',
             'adminurl'  : adminurl,
             'filterurl' : adminurl + '/privacy/sender',
             }
        if sender:
            d['description'] = _("all the %(esender)s's held messages.")
            doc.AddItem(Utils.maketext('admindbpreamble.html', d,
                                       raw=1, mlist=mlist))
            show_sender_requests(mlist, form, sender)
        elif msgid:
            d['description'] = _('a single held message.')
            doc.AddItem(Utils.maketext('admindbpreamble.html', d,
                                       raw=1, mlist=mlist))
            show_message_requests(mlist, form, msgid)
        elif details == 'all':
            d['description'] = _('all held messages.')
            doc.AddItem(Utils.maketext('admindbpreamble.html', d,
                                       raw=1, mlist=mlist))
            show_detailed_requests(mlist, form)
        elif details == 'instructions':
            doc.AddItem(Utils.maketext('admindbdetails.html', d,
                                       raw=1, mlist=mlist))
        else:
            # Show a summary of all requests
            doc.AddItem(Utils.maketext('admindbsummary.html', d,
                                       raw=1, mlist=mlist))
            show_pending_subs(mlist, form)
            show_pending_unsubs(mlist, form)
            show_helds_overview(mlist, form)
        # Finish up the document, adding buttons to the form
        if not details:
            doc.AddItem(form)
            form.AddItem('<hr>')
            form.AddItem(Center(SubmitButton('submit', _('Submit All Data'))))
        doc.AddItem(mlist.GetMailmanFooter())
        print doc.Format()
        # Commit all changes
        mlist.Save()
    finally:
        mlist.Unlock()



def handle_no_list(msg=''):
    # Print something useful if no list was given.
    doc = Document()
    doc.set_language(mm_cfg.DEFAULT_SERVER_LANGUAGE)

    header = _('Mailman Administrative Database Error')
    doc.SetTitle(header)
    doc.AddItem(Header(2, header))
    doc.AddItem(msg)
    url = Utils.ScriptURL('admin', absolute=1)
    link = Link(url, _('list of available mailing lists.')).Format()
    doc.AddItem(_('You must specify a list name.  Here is the %(link)s'))
    doc.AddItem('<hr>')
    doc.AddItem(MailmanLogo())
    print doc.Format()



def show_pending_subs(mlist, form):
    # Add the subscription request section
    pendingsubs = mlist.GetSubscriptionIds()
    if not pendingsubs:
        return
    form.AddItem('<hr>')
    form.AddItem(Center(Header(2, _('Subscription Requests'))))
    table = Table(border=2)
    table.AddRow([Center(Bold(_('User address/name'))),
                  Center(Bold(_('Your decision'))),
                  Center(Bold(_('Reason for refusal')))
                  ])
    for id in pendingsubs:
        time, addr, fullname, passwd, digest, lang = mlist.GetRecord(id)
        table.AddRow(['%s<br><em>%s</em>' % (addr, fullname),
                      RadioButtonArray(id, (_('Defer'),
                                            _('Approve'),
                                            _('Reject'),
                                            _('Discard')),
                                       values=(mm_cfg.DEFER,
                                               mm_cfg.SUBSCRIBE,
                                               mm_cfg.REJECT,
                                               mm_cfg.DISCARD),
                                       checked=0),
                      TextBox('comment-%d' % id, size=45)
                      ])
    form.AddItem(table)

    

def show_pending_unsubs(mlist, form):
    # Add the pending unsubscription request section
    pendingunsubs = mlist.GetUnsubscriptionIds()
    if not pendingunsubs:
        return
    form.AddItem('<hr>')
    form.AddItem(Center(Header(2, _('Unsubscription Requests'))))
    table = Table(border=2)
    table.AddRow([Center(Bold(_('User address/name'))),
                  Center(Bold(_('Your decision'))),
                  Center(Bold(_('Reason for refusal')))
                  ])
    for id in pendingunsubs:
        addr = mlist.GetRecord(id)
        fullname = mlist.getMemberName(addr)
        if fullname is None:
            fullname = ''
        table.AddRow(['%s<br><em>%s</em>' % (addr, fullname),
                      RadioButtonArray(id, (_('Defer'),
                                            _('Approve'),
                                            _('Reject'),
                                            _('Discard')),
                                       values=(mm_cfg.DEFER,
                                               mm_cfg.UNSUBSCRIBE,
                                               mm_cfg.REJECT,
                                               mm_cfg.DISCARD),
                                       checked=0),
                      TextBox('comment-%d' % id, size=45)
                      ])
    form.AddItem(table)



def show_helds_overview(mlist, form):
    # Sort the held messages by sender
    bysender = helds_by_sender(mlist)
    if not bysender:
        return
    # Add the by-sender overview tables
    admindburl = mlist.GetScriptURL('admindb', absolute=1)
    table = Table(border=0)
    form.AddItem(table)
    senders = bysender.keys()
    senders.sort()
    for sender in senders:
        qsender = quote_plus(sender)
        esender = cgi.escape(sender)
        senderurl = admindburl + '?sender=' + qsender
        # The encompassing sender table
        stable = Table(border=1)
        stable.AddRow([Center(Bold(_('From:')).Format() + esender)])
        stable.AddCellInfo(stable.GetCurrentRowIndex(), 0, colspan=2)
        left = Table(border=0)
        left.AddRow([_('Action to take on all these held messages:')])
        left.AddCellInfo(left.GetCurrentRowIndex(), 0, colspan=2)
        btns = hacky_radio_buttons(
            'senderaction-' + qsender,
            (_('Defer'), _('Accept'), _('Reject'), _('Discard')),
            (mm_cfg.DEFER, mm_cfg.APPROVE, mm_cfg.REJECT, mm_cfg.DISCARD),
            (1, 0, 0, 0))
        left.AddRow([btns])
        left.AddCellInfo(left.GetCurrentRowIndex(), 0, colspan=2)
        left.AddRow([
            CheckBox('senderpreserve-' + qsender, 1).Format() +
            '&nbsp;' +
            _('Preserve messages for the site administrator')
            ])
        left.AddCellInfo(left.GetCurrentRowIndex(), 0, colspan=2)
        left.AddRow([
            CheckBox('senderforward-' + qsender, 1).Format() +
            '&nbsp;' +
            _('Forward messages (individually) to:')
            ])
        left.AddCellInfo(left.GetCurrentRowIndex(), 0, colspan=2)
        left.AddRow([
            TextBox('senderforwardto-' + qsender,
                    value=mlist.GetOwnerEmail())
            ])
        left.AddCellInfo(left.GetCurrentRowIndex(), 0, colspan=2)
        # Ask if this address should be added to one of the sender filters,
        # but only if it isn't already in one of the filters.
        if sender not in (mlist.accept_these_nonmembers +
                          mlist.hold_these_nonmembers +
                          mlist.reject_these_nonmembers +
                          mlist.discard_these_nonmembers):
            left.AddRow([
                CheckBox('senderfilterp-' + qsender, 1).Format() +
                '&nbsp;' +
                _('Add <b>%(esender)s</b> to a sender filter')
                ])
            left.AddCellInfo(left.GetCurrentRowIndex(), 0, colspan=2)
            btns = hacky_radio_buttons(
                'senderfilter-' + qsender,
                (_('Accepts'), _('Holds'), _('Rejects'), _('Discards')),
                (mm_cfg.ACCEPT, mm_cfg.HOLD, mm_cfg.REJECT, mm_cfg.DISCARD),
                (0, 0, 0, 1))
            left.AddRow([btns])
            left.AddCellInfo(left.GetCurrentRowIndex(), 0, colspan=2)
        right = Table(border=0)
        right.AddRow([
            _("""Click on the message number to view the individual
            message, or you can """) +
            Link(senderurl, _('view all messages from %(esender)s')).Format()
            ])
        right.AddCellInfo(right.GetCurrentRowIndex(), 0, colspan=2)
        right.AddRow(['&nbsp;', '&nbsp;'])
        counter = 1
        for id in bysender[sender]:
            info = mlist.GetRecord(id)
            if len(info) == 5:
                ptime, sender, subject, reason, filename = info
                msgdata = {}
            else:
                ptime, sender, subject, reason, filename, msgdata = info
            # BAW: This is really the size of the message pickle, which should
            # be close, but won't be exact.  Sigh, good enough.
            try:
                size = os.path.getsize(os.path.join(mm_cfg.DATA_DIR, filename))
            except OSError, e:
                if e.errno <> errno.ENOENT: raise
                # This message must have gotten lost, i.e. it's already been
                # handled by the time we got here.
                mlist.HandleRequest(id, mm_cfg.DISCARD)
                continue
            t = Table(border=0)
            t.AddRow([Link(admindburl + '?msgid=%d' % id, '[%d]' % counter),
                      Bold(_('Subject:')),
                      cgi.escape(subject)
                      ])
            t.AddRow(['&nbsp;', Bold(_('Size:')), str(size) + _(' bytes')])
            t.AddRow(['&nbsp;', Bold(_('Reason:')),
                      reason or _('not available')])
            counter += 1
            right.AddRow([t])
        stable.AddRow([left, right])
        table.AddRow([stable])



def show_sender_requests(mlist, form, sender):
    bysender = helds_by_sender(mlist)
    if not bysender:
        return
    sender_ids = bysender.get(sender)
    if sender_ids is None:
        # BAW: should we print an error message?
        return
    total = len(sender_ids)
    count = 1
    for id in sender_ids:
        info = mlist.GetRecord(id)
        show_post_requests(mlist, id, info, total, count, form)
        count += 1



def show_message_requests(mlist, form, id):
    try:
        id = int(id)
        info = mlist.GetRecord(id)
    except (ValueError, KeyError):
        # BAW: print an error message?
        return
    show_post_requests(mlist, id, info, 1, 1, form)



def show_detailed_requests(mlist, form):
    all = mlist.GetHeldMessageIds()
    total = len(all)
    count = 1
    for id in mlist.GetHeldMessageIds():
        info = mlist.GetRecord(id)
        show_post_requests(mlist, id, info, total, count, form)
        count += 1



def show_post_requests(mlist, id, info, total, count, form):
    # For backwards compatibility with pre 2.0beta3
    if len(info) == 5:
        ptime, sender, subject, reason, filename = info
        msgdata = {}
    else:
        ptime, sender, subject, reason, filename, msgdata = info
    form.AddItem('<hr>')
    # Header shown on each held posting (including count of total)
    msg = _('Posting Held for Approval')
    if total <> 1:
        msg += _(' (%(count)d of %(total)d)')
    form.AddItem(Center(Header(2, msg)))
    # We need to get the headers and part of the textual body of the message
    # being held.  The best way to do this is to use the email Parser to get
    # an actual object, which will be easier to deal with.  We probably could
    # just do raw reads on the file.
    try:
        msg = readMessage(os.path.join(mm_cfg.DATA_DIR, filename))
    except IOError, e:
        if e.errno <> errno.ENOENT:
            raise
        form.AddItem(_('<em>Message with id #%(id)d was lost.'))
        form.AddItem('<p>')
        # BAW: kludge to remove id from requests.db.
        try:
            mlist.HandleRequest(id, mm_cfg.DISCARD)
        except Errors.LostHeldMessage:
            pass
        return
    except email.Errors.MessageParseError:
        form.AddItem(_('<em>Message with id #%(id)d is corrupted.'))
        # BAW: Should we really delete this, or shuttle it off for site admin
        # to look more closely at?
        form.AddItem('<p>')
        # BAW: kludge to remove id from requests.db.
        try:
            mlist.HandleRequest(id, mm_cfg.DISCARD)
        except Errors.LostHeldMessage:
            pass
        return
    # Get the header text and the message body excerpt
    lines = []
    chars = 0
    # A negative value means, include the entire message regardless of size
    limit = mm_cfg.ADMINDB_PAGE_TEXT_LIMIT
    for line in email.Iterators.body_line_iterator(msg):
        lines.append(line)
        chars += len(line)
        if chars > limit > 0:
            break
    # Negative values mean display the entire message, regardless of size
    if limit > 0:
        body = EMPTYSTRING.join(lines)[:mm_cfg.ADMINDB_PAGE_TEXT_LIMIT]
    else:
        body = EMPTYSTRING.join(lines)
    hdrtxt = NL.join(['%s: %s' % (k, v) for k, v in msg.items()])

    # Okay, we've reconstituted the message just fine.  Now for the fun part!
    t = Table(cellspacing=0, cellpadding=0, width='100%')
    t.AddRow([Bold(_('From:')), sender])
    row, col = t.GetCurrentRowIndex(), t.GetCurrentCellIndex()
    t.AddCellInfo(row, col-1, align='right')
    t.AddRow([Bold(_('Subject:')), cgi.escape(subject)])
    t.AddCellInfo(row+1, col-1, align='right')
    t.AddRow([Bold(_('Reason:')), _(reason)])
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
    t.AddRow([Bold(_('Message Headers:')),
              TextArea('headers-%d' % id, hdrtxt,
                       rows=10, cols=80)])
    row, col = t.GetCurrentRowIndex(), t.GetCurrentCellIndex()
    t.AddCellInfo(row, col-1, align='right')
    t.AddRow([Bold(_('Message Excerpt:')),
              TextArea('fulltext-%d' % id, cgi.escape(body),
                       rows=10, cols=80)])
    t.AddCellInfo(row+1, col-1, align='right')
    form.AddItem(t)
    form.AddItem('<p>')



def process_form(mlist, doc, cgidata):
    senderactions = {}
    # Sender-centric actions
    for k in cgidata.keys():
        for prefix in ('senderaction-', 'senderpreserve-', 'senderforward-',
                       'senderforwardto-', 'senderfilterp-', 'senderfilter-'):
            if k.startswith(prefix):
                action = k[:len(prefix)-1]
                sender = unquote_plus(k[len(prefix):])
                value = cgidata.getvalue(k)
                senderactions.setdefault(sender, {})[action] = value
    for sender in senderactions.keys():
        actions = senderactions[sender]
        # Handle what to do about all this sender's held messages
        try:
            action = int(actions.get('senderaction', mm_cfg.DEFER))
        except ValueError:
            action = mm_cfg.DEFER
        if action in (mm_cfg.DEFER, mm_cfg.APPROVE,
                      mm_cfg.REJECT, mm_cfg.DISCARD):
            preserve = actions.get('senderpreserve', 0)
            forward = actions.get('senderforward', 0)
            forwardaddr = actions.get('senderforwardto', '')
            comment = _('No reason given')
            bysender = helds_by_sender(mlist)
            for id in bysender.get(sender, []):
                try:
                    mlist.HandleRequest(id, action, comment, preserve,
                                        forward, forwardaddr)
                except (KeyError, Errors.LostHeldMessage):
                    # That's okay, it just means someone else has already
                    # updated the database while we were staring at the page,
                    # so just ignore it
                    continue
        # Now see if this sender should be added to one of the nonmember
        # sender filters.
        if actions.get('senderfilterp', 0):
            try:
                which = int(actions.get('senderfilter'))
            except ValueError:
                # Bogus form
                which = 'ignore'
            if which == mm_cfg.ACCEPT:
                mlist.accept_these_nonmembers.append(sender)
            elif which == mm_cfg.HOLD:
                mlist.hold_these_nonmembers.append(sender)
            elif which == mm_cfg.REJECT:
                mlist.reject_these_nonmembers.append(sender)
            elif which == mm_cfg.DISCARD:
                mlist.discard_these_nonmembers.append(sender)
            # Otherwise, it's a bogus form, so ignore it
    # Now, do message specific actions
    erroraddrs = []
    for k in cgidata.keys():
        formv = cgidata[k]
        if type(formv) == ListType:
            continue
        try:
            v = int(formv.value)
            request_id = int(k)
        except ValueError:
            continue
        if v not in (mm_cfg.DEFER, mm_cfg.APPROVE,
                     mm_cfg.REJECT, mm_cfg.DISCARD):
            continue
        # Get the action comment and reasons if present.
        commentkey = 'comment-%d' % request_id
        preservekey = 'preserve-%d' % request_id
        forwardkey = 'forward-%d' % request_id
        forwardaddrkey = 'forward-addr-%d' % request_id
        # Defaults
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
        # Handle the request id
        try:
            mlist.HandleRequest(request_id, v, comment,
                                preserve, forward, forwardaddr)
        except (KeyError, Errors.LostHeldMessage):
            # That's okay, it just means someone else has already updated the
            # database while we were staring at the page, so just ignore it
            continue
        except Errors.MMAlreadyAMember, v:
            erroraddrs.append(v)
    # save the list and print the results
    doc.AddItem(Header(2, _('Database Updated...')))
    if erroraddrs:
        for addr in erroraddrs:
            doc.AddItem(`addr` + _(' is already a member') + '<br>')
