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

"""Add the message to the archives."""

import string
from Mailman import mm_cfg



def process(mlist, msg):
    # short circuits
    if getattr(msg, 'isdigest', 0):
        return
    archivep = msg.getheader('x-archive')
    if archivep and string.lower(archivep) == 'no':
        return
    # TBD: this needs to be converted to the new pipeline machinery
    mlist.ArchiveMail(msg)
