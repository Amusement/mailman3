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

"""Language manager."""

from __future__ import unicode_literals

__metaclass__ = type
__all__ = [
    'LanguageManager',
    ]

from zope.interface import implements
from mailman.interfaces.languages import ILanguageManager



class LanguageManager:
    implements(ILanguageManager)

    def __init__(self):
        self._language_data = {}
        self._enabled = set()

    def add_language(self, code, description, charset, enable=True):
        self._language_data[code] = (description, charset)
        if enable:
            self._enabled.add(code)

    def enable_language(self, code):
        if code not in self._language_data:
            raise KeyError(code)
        self._enabled.add(code)

    def get_description(self, code):
        return self._language_data[code][0]

    def get_charset(self, code):
        return self._language_data[code][1]

    @property
    def known_codes(self):
        return iter(self._language_data)

    @property
    def enabled_codes(self):
        return iter(self._enabled)

    @property
    def enabled_names(self):
        for code in self._enabled:
            description, charset = self._language_data[code]
            yield description
