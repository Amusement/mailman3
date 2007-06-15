# Copyright (C) 2007 by the Free Software Foundation, Inc.
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

import sys

from sqlalchemy import types



# SQLAlchemy custom type for storing enums in the database.
class EnumType(types.TypeDecorator):
    # Enums can be stored as strings of the form:
    # full.path.to.Enum:intval
    impl = types.String

    def convert_bind_param(self, value, engine):
        if value is None:
            return None
        return '%s:%s.%d' % (value.enumclass.__module__,
                             value.enumclass.__name__,
                             int(value))

    def convert_result_value(self, value, engine):
        if value is None:
            return None
        path, intvalue = value.rsplit(':', 1)
        modulename, classname = intvalue.rsplit('.', 1)
        __import__(modulename)
        cls = getattr(sys.modules[modulename], classname)
        return cls[int(intvalue)]
