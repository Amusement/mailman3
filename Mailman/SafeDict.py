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

"""A `safe' dictionary for string interpolation."""

from types import StringType
from UserDict import UserDict



class SafeDict(UserDict):
    """Dictionary which returns a default value for unknown keys.

    This is used in maketext so that editing templates is a bit more robust.
    """
    def __init__(self, d=None):
        # optional initial dictionary is a Python 1.5.2-ism.  Do it this way
        # for portability
        UserDict.__init__(self)
        if d is not None:
            self.update(d)

    def __getitem__(self, key):
        try:
            return self.data[key]
        except KeyError:
            if type(key) == StringType:
                return '%('+key+')s'
            else:
                return '<Missing key: %s>' % `key`
