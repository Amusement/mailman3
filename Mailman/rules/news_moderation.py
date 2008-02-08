# Copyright (C) 2007-2008 by the Free Software Foundation, Inc.
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

"""The news moderation rule."""

__all__ = ['ModeratedNewsgroup']
__metaclass__ = type


from zope.interface import implements

from Mailman.i18n import _
from Mailman.interfaces import IRule, NewsModeration



class ModeratedNewsgroup:
    """The news moderation rule."""
    implements(IRule)

    name = 'news-moderation'
    description = _(
        u"""Match all messages posted to a mailing list that gateways to a
        moderated newsgroup.
        """)
    record = True

    def check(self, mlist, msg, msgdata):
        """See `IRule`."""
        return mlist.news_moderation == NewsModeration.moderated