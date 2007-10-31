# Copyright (C) 2006-2007 by the Free Software Foundation, Inc.
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

from elixir import *
from email.utils import formataddr
from zope.interface import implements

from Mailman.database.types import EnumType
from Mailman.interfaces import IPreferences

ADDRESS_KIND    = 'Mailman.database.model.address.Address'
MEMBER_KIND     = 'Mailman.database.model.member.Member'
USER_KIND       = 'Mailman.database.model.user.User'



class Preferences(Entity):
    implements(IPreferences)

    acknowledge_posts = Field(Boolean)
    hide_address = Field(Boolean)
    preferred_language = Field(Unicode)
    receive_list_copy = Field(Boolean)
    receive_own_postings = Field(Boolean)
    delivery_mode = Field(EnumType)
    delivery_status = Field(EnumType)

    def __repr__(self):
        return '<Preferences object at %#x>' % id(self)
