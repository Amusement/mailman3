# Copyright (C) 1998-2009 by the Free Software Foundation, Inc.
#
# This file is part of GNU Mailman.
#
# GNU Mailman is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# GNU Mailman is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# GNU Mailman.  If not, see <http://www.gnu.org/licenses/>.

"""Handler for auto-responses."""

from __future__ import absolute_import, unicode_literals

__metaclass__ = type
__all__ = [
    'Replybot',
    ]


import logging
import datetime

from zope.interface import implements

from mailman import Utils
from mailman.config import config
from mailman.email.message import Message, UserNotification
from mailman.i18n import _
from mailman.interfaces.autorespond import IAutoResponseSet, Response
from mailman.interfaces.handler import IHandler
from mailman.utilities.datetime import today
from mailman.utilities.string import expand


log = logging.getLogger('mailman.error')
NODELTA = datetime.timedelta()



def process(mlist, msg, msgdata):
    # Normally, the replybot should get a shot at this message, but there are
    # some important short-circuits, mostly to suppress 'bot storms, at least
    # for well behaved email bots (there are other governors for misbehaving
    # 'bots).  First, if the original message has an "X-Ack: No" header, we
    # skip the replybot.  Then, if the message has a Precedence header with
    # values bulk, junk, or list, and there's no explicit "X-Ack: yes" header,
    # we short-circuit.  Finally, if the message metadata has a true 'noack'
    # key, then we skip the replybot too.
    ack = msg.get('x-ack', '').lower()
    if ack == 'no' or msgdata.get('noack'):
        return
    precedence = msg.get('precedence', '').lower()
    if ack <> 'yes' and precedence in ('bulk', 'junk', 'list'):
        return
    # Check to see if the list is even configured to autorespond to this email
    # message.  Note: the mailowner script sets the `toadmin' or `toowner' key
    # (which for replybot purposes are equivalent), and the mailcmd script
    # sets the `torequest' key.
    toadmin = msgdata.get('toowner')
    torequest = msgdata.get('torequest')
    if ((toadmin and not mlist.autorespond_admin) or
        (torequest and not mlist.autorespond_requests) or \
        (not toadmin and not torequest and not mlist.autorespond_postings)):
        return
    # Now see if we're in the grace period for this sender.  graceperiod <= 0
    # means always autorespond, as does an "X-Ack: yes" header (useful for
    # debugging).
    response_set = IAutoResponseSet(mlist)
    address = config.db.user_manager.get_address(msg.sender)
    if address is None:
        address = config.db.user_manager.create_address(msg.sender)
    grace_period = mlist.autoresponse_graceperiod
    if grace_period > NODELTA and ack <> 'yes':
        if toadmin:
            last = response_set.last_response(address, Response.owner)
        elif torequest:
            last = response_set.last_response(address, Response.command)
        else:
            last = response_set.last_response(address, Response.postings)
        if last is not None and last.date_sent + grace_period > today():
            return
    # Okay, we know we're going to auto-respond to this sender, craft the
    # message, send it, and update the database.
    realname = mlist.real_name
    subject = _(
        'Auto-response for your message to the "$realname" mailing list')
    # Do string interpolation into the autoresponse text
    d = dict(listname       = realname,
             listurl        = mlist.script_url('listinfo'),
             requestemail   = mlist.request_address,
             owneremail     = mlist.owner_address,
             )
    if toadmin:
        rtext = mlist.autoresponse_admin_text
    elif torequest:
        rtext = mlist.autoresponse_request_text
    else:
        rtext = mlist.autoresponse_postings_text
    # Interpolation and Wrap the response text.
    text = Utils.wrap(expand(rtext, d))
    outmsg = UserNotification(msg.sender, mlist.bounces_address,
                              subject, text, mlist.preferred_language)
    outmsg['X-Mailer'] = _('The Mailman Replybot')
    # prevent recursions and mail loops!
    outmsg['X-Ack'] = 'No'
    outmsg.send(mlist)
    # update the grace period database
    if grace_period > NODELTA:
        # graceperiod is in days, we need # of seconds
        if toadmin:
            response_set.response_sent(address, Response.owner)
        elif torequest:
            response_set.response_sent(address, Response.command)
        else:
            response_set.response_sent(address, Response.postings)



class Replybot:
    """Send automatic responses."""

    implements(IHandler)

    name = 'replybot'
    description = _('Send automatic responses.')

    def process(self, mlist, msg, msgdata):
        """See `IHandler`."""
        process(mlist, msg, msgdata)
