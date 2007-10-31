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

"""Harness for testing Mailman's documentation."""

import os
import pdb
import doctest
import unittest

import Mailman

from Mailman.app.styles import style_manager
from Mailman.configuration import config
from Mailman.database import flush


COMMASPACE = ', '



def cleaning_teardown(testobj):
    """Clear all persistent data at the end of a doctest."""
    # Clear the database of all rows.
    config.db._reset()
    flush()
    # Remove all but the default style.
    for style in style_manager.styles:
        if style.name <> 'default':
            style_manager.unregister(style)
    # Remove all queue files.
    for dirpath, dirnames, filenames in os.walk(config.QUEUE_DIR):
        for filename in filenames:
            os.remove(os.path.join(dirpath, filename))
    # Clear out messages in the message store directory.
    for dirpath, dirnames, filenames in os.walk(config.MESSAGES_DIR):
        for filename in filenames:
            os.remove(os.path.join(dirpath, filename))



def test_suite():
    suite = unittest.TestSuite()
    docsdir = os.path.join(os.path.dirname(Mailman.__file__), 'docs')
    # Under higher verbosity settings, report all doctest errors, not just the
    # first one.
    flags = (doctest.ELLIPSIS |
             doctest.NORMALIZE_WHITESPACE |
             doctest.REPORT_NDIFF)
    if config.opts.verbosity <= 2:
        flags |= doctest.REPORT_ONLY_FIRST_FAILURE
    for filename in os.listdir(docsdir):
        if os.path.splitext(filename)[1] == '.txt':
            test = doctest.DocFileSuite(
                'docs/' + filename,
                package=Mailman,
                optionflags=flags,
                tearDown=cleaning_teardown)
            suite.addTest(test)
    return suite
