# Copyright (C) 2007-2009 by the Free Software Foundation, Inc.
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

__metaclass__ = type
__all__ = [
    'Message',
    ]

from storm.locals import *
from zope.interface import implements

from mailman.config import config
from mailman.database.model import Model
from mailman.interfaces.messages import IMessage



class Message(Model):
    """A message in the message store."""

    implements(IMessage)

    id = Int(primary=True, default=AutoReload)
    message_id = Unicode()
    message_id_hash = RawStr()
    path = RawStr()
    # This is a Messge-ID field representation, not a database row id.

    def __init__(self, message_id, message_id_hash, path):
        super(Message, self).__init__()
        self.message_id = message_id
        self.message_id_hash = message_id_hash
        self.path = path
        config.db.store.add(self)
