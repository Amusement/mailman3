# Copyright (C) 2008 by the Free Software Foundation, Inc.
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301,
# USA.

"""Prototypical permalinking archiver."""

__metaclass__ = type
__all__ = [
    'Prototype',
    ]


import hashlib

from base64 import b32encode
from urlparse import urljoin
from zope.interface import implements

from mailman.configuration import config
from mailman.interfaces.archiver import IArchiver



class Prototype:
    """A prototype of a third party archiver.

    Mailman proposes a draft specification for interoperability between list
    servers and archivers: <http://wiki.list.org/display/DEV/Stable+URLs>.
    """

    implements(IArchiver)

    name = 'prototype'
    is_enabled = False

    @staticmethod
    def list_url(mlist):
        """See `IArchiver`."""
        web_host = config.domains.get(mlist.host_name, mlist.host_name)
        return 'http://' + web_host

    @staticmethod
    def permalink(mlist, msg):
        """See `IArchiver`."""
        message_id = msg.get('message-id')
        # It is not the archiver's job to ensure the message has a Message-ID.
        assert message_id is not None, 'No Message-ID found'
        # The angle brackets are not part of the Message-ID.  See RFC 2822.
        if message_id.startswith('<') and message_id.endswith('>'):
            message_id = message_id[1:-1]
        digest = hashlib.sha1(message_id).digest()
        message_id_hash = b32encode(digest)
        del msg['x-message-id-hash']
        msg['X-Message-ID-Hash'] = message_id_hash
        return urljoin(Prototype.list_url(mlist), message_id_hash)

    @staticmethod
    def archive_message(mlist, message):
        """See `IArchiver`."""
        raise NotImplementedError
