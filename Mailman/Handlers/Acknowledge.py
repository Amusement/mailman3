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

"""Send an acknowledgement of the successful post to the sender.

This only happens if the sender has set their AcknowledgePosts attribute.
This module must appear after the deliverer in the message pipeline in order
to send acks only after successful delivery.

"""

from Mailman import mm_cfg
from Mailman import Utils
from Mailman import Message
from Mailman.i18n import _



def process(mlist, msg, msgdata):
    # Extract the sender's address and find them in the user database
    sender = msgdata.get('original_sender', msg.get_sender())
    sender = mlist.FindUser(sender)
    if sender and mlist.GetUserOption(sender, mm_cfg.AcknowledgePosts):
        # Okay, they want acknowledgement of their post
        subject = msg['subject']
        # Trim off the subject prefix
        if subject:
            prefix = mlist.subject_prefix
            if subject.startswith(prefix):
                subject = subject[len(prefix):]
        # Get the text from the template
        pluser = mlist.GetPreferredLanguage(sender)
        # BAW: I don't like using $LANG
        os.environ['LANG'] = pluser
        realname = mlist.real_name
        text = Utils.maketext(
            'postack.txt',
            {'subject'     : subject,
             'listname'    : realname,
             'listinfo_url': mlist.GetScriptURL('listinfo', absolute=1),
             }, pluser)
        # Craft the outgoing message, with all headers and attributes
        # necessary for general delivery.  Then enqueue it to the outgoing
        # queue.
        subject = _('%(realname)s post acknowledgement')
        usermsg = Message.UserNotification(sender, mlist.GetAdminEmail(),
                                           subject, text)
        usermsg.send(mlist)
