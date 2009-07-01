# Copyright (C) 2000-2009 by the Free Software Foundation, Inc.
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

"""Internationalization support."""

from __future__ import unicode_literals

__metaclass__ = type
__all__ = [
    '_',
    'get_translation',
    'set_language',
    'set_translation',
    'using_language',
    ]


import os
import sys
import time
import string
import gettext

import mailman.messages
from mailman.utilities.string import expand

_translation = None
_missing = object()

MESSAGES_DIR = os.path.dirname(mailman.messages.__file__)



class Template(string.Template):
    """Match any attribute path."""
    idpattern = r'[_a-z][_a-z0-9.]*'


class attrdict(dict):
    """Follow attribute paths."""
    def __getitem__(self, key):
        parts = key.split('.')
        value = super(attrdict, self).__getitem__(parts.pop(0))
        while parts:
            value = getattr(value, parts.pop(0), _missing)
            if value is _missing:
                raise KeyError(key)
        return value



def set_language(language_code=None):
    """Set the global translation context from a language code.

    :param language_code: The two letter language code to set.
    :type language_code: str
    """
    # pylint: disable-msg=W0603
    global _translation
    # gettext.translation() API requires None or a sequence.
    codes = (None if language_code is None else [language_code])
    try:
        _translation = gettext.translation('mailman', MESSAGES_DIR, codes)
    except IOError:
        # The selected language was not installed in messages, so fall back to
        # untranslated English.
        _translation = gettext.NullTranslations()


def get_translation():
    """Return the global translation context.

    :return: The global translation context.
    :rtype: `GNUTranslation`
    """
    return _translation


def set_translation(translation):
    """Set the global translation context.

    :param translation: The translation context.
    :type translation: `GNUTranslation`.
    """
    # pylint: disable-msg=W0603
    global _translation
    _translation = translation


class using_language:
    """Context manager for Python's `with` statement."""
    def __init__(self, language_code):
        self._language_code = language_code
        self._old_translation = None

    def __enter__(self):
        self._old_translation = _translation
        set_language(self._language_code)

    # pylint: disable-msg=W0613
    def __exit__(self, *exc_info):
        # pylint: disable-msg=W0603
        global _translation
        _translation = self._old_translation
        # Do not suppress exceptions.
        return False


# Set up the global translation based on environment variables.  Mostly used
# for command line scripts.
if _translation is None:
    _translation = gettext.NullTranslations()



def _(s):
    """Translate the string.

    :param s: The string to transate
    :type s: string
    :return: The translated string
    :rtype: string
    """
    if s == '':
        return ''
    assert s, 'Cannot translate: {0}'.format(s)
    # Do translation of the given string into the current language, and do PEP
    # 292 style $-string interpolation into the resulting string.
    #
    # This lets you write something like:
    #
    #     now = time.ctime(time.time())
    #     print _('The current time is: $now')
    #
    # and have it Just Work.  Note that the lookup order for keys in the
    # original string is 1) locals dictionary, 2) globals dictionary.
    #
    # Get the frame of the caller.
    # pylint: disable-msg=W0212
    frame = sys._getframe(1)
    # A `safe' dictionary is used so we won't get an exception if there's a
    # missing key in the dictionary.
    raw_dict = frame.f_globals.copy()
    raw_dict.update(frame.f_locals)
    # Mailman must be unicode safe internally (i.e. all strings inside Mailman
    # must be unicodes).  The translation service is one boundary to the
    # outside world, so to honor this constraint, make sure that all strings
    # to come out of _() are unicodes, even if the translated string or
    # dictionary values are 8-bit strings.
    tns = _translation.ugettext(s)
    charset = _translation.charset() or 'us-ascii'
    # Python requires ** dictionaries to have str, not unicode keys.  For our
    # purposes, keys should always be ascii.  Values though should be unicode.
    translated_string = expand(tns, attrdict(raw_dict), Template)
    if isinstance(translated_string, str):
        translated_string = unicode(translated_string, charset)
    return translated_string



def ctime(date):
    """Translate a ctime.

    :param date: The date to translate.
    :type date: str or time float
    :return: The translated date.
    :rtype: string
    """
    # Don't make these module globals since we have to do runtime translation
    # of the strings anyway.
    daysofweek = [
        _('Mon'), _('Tue'), _('Wed'), _('Thu'),
        _('Fri'), _('Sat'), _('Sun')
        ]
    months = [
        '',
        _('Jan'), _('Feb'), _('Mar'), _('Apr'), _('May'), _('Jun'),
        _('Jul'), _('Aug'), _('Sep'), _('Oct'), _('Nov'), _('Dec')
        ]

    # pylint: disable-msg=W0612
    tzname = _('Server Local Time')
    if isinstance(date, str):
        try:
            year, mon, day, hh, mm, ss, wday, ydat, dst = time.strptime(date)
            if dst in (0, 1):
                tzname = time.tzname[dst]
            else:
                # MAS: No exception but dst = -1 so try
                return ctime(time.mktime((year, mon, day, hh, mm, ss, wday,
                                          ydat, dst)))
        except (ValueError, AttributeError):
            try:
                wday, mon, day, hms, year = date.split()
                hh, mm, ss = hms.split(':')
                year = int(year)
                day = int(day)
                hh = int(hh)
                mm = int(mm)
                ss = int(ss)
            except ValueError:
                return date
            else:
                for i in range(0, 7):
                    wconst = (1999, 1, 1, 0, 0, 0, i, 1, 0)
                    if wday.lower() == time.strftime('%a', wconst).lower():
                        wday = i
                        break
                for i in range(1, 13):
                    mconst = (1999, i, 1, 0, 0, 0, 0, 1, 0)
                    if mon.lower() == time.strftime('%b', mconst).lower():
                        mon = i
                        break
    else:
        # pylint: disable-msg=W0612
        year, mon, day, hh, mm, ss, wday, yday, dst = time.localtime(date)
        if dst in (0, 1):
            tzname = time.tzname[dst]

    wday = daysofweek[wday]
    mon = months[mon]
    return _('$wday $mon $day $hh:$mm:$ss $tzname $year')
