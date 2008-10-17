# Copyright (C) 2007-2008 by the Free Software Foundation, Inc.
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

"""Harness for testing Mailman's documentation."""

import os
import random
import doctest
import unittest

from email import message_from_string

import mailman

from mailman.Message import Message
from mailman.configuration import config
from mailman.core.styles import style_manager
from mailman.testing.helpers import SMTPServer


DOT = '.'
COMMASPACE = ', '



def specialized_message_from_string(text):
    """Parse text into a message object.

    This is specialized in the sense that an instance of Mailman's own Message
    object is returned, and this message object has an attribute
    `original_size` which is the pre-calculated size in bytes of the message's
    text representation.
    """
    # This mimic what Switchboard.dequeue() does when parsing a message from
    # text into a Message instance.
    original_size = len(text)
    message = message_from_string(text, Message)
    message.original_size = original_size
    return message


def stop():
    """Call into pdb.set_trace()"""
    # Do the import here so that you get the wacky special hacked pdb instead
    # of Python's normal pdb.
    import pdb
    pdb.set_trace()


def setup(testobj):
    """Test setup."""
    smtpd = SMTPServer()
    smtpd.start()
    # In general, I don't like adding convenience functions, since I think
    # doctests should do the imports themselves.  It makes for better
    # documentation that way.  However, a few are really useful, or help to
    # hide some icky test implementation details.
    testobj.globs['message_from_string'] = specialized_message_from_string
    testobj.globs['commit'] = config.db.commit
    testobj.globs['smtpd'] = smtpd
    testobj.globs['stop'] = stop
    # Stash the current state of the global domains away for restoration in
    # the teardown.
    testobj._domains = config.domains.copy()



def cleaning_teardown(testobj):
    """Clear all persistent data at the end of a doctest."""
    # Clear the database of all rows.
    config.db._reset()
    # Reset the global domains.
    config.domains = testobj._domains
    # Remove all but the default style.
    for style in style_manager.styles:
        if style.name <> 'default':
            style_manager.unregister(style)
    # Remove all queue files.
    for dirpath, dirnames, filenames in os.walk(config.QUEUE_DIR):
        for filename in filenames:
            os.remove(os.path.join(dirpath, filename))
    # Clear out messages in the message store.
    for message in config.db.message_store.messages:
        config.db.message_store.delete_message(message['message-id'])
    config.db.commit()
    # Reset all archivers by disabling them.
    for archiver in config.archivers.values():
        archiver.is_enabled = False
    # Shutdown the smtp server.
    smtpd = testobj.globs['smtpd']
    smtpd.clear()
    smtpd.stop()



def test_suite():
    suite = unittest.TestSuite()
    topdir = os.path.dirname(mailman.__file__)
    packages = []
    for dirpath, dirnames, filenames in os.walk(topdir):
        if 'docs' in dirnames:
            docsdir = os.path.join(dirpath, 'docs')[len(topdir)+1:]
            packages.append(docsdir)
    # Under higher verbosity settings, report all doctest errors, not just the
    # first one.
    flags = (doctest.ELLIPSIS |
             doctest.NORMALIZE_WHITESPACE |
             doctest.REPORT_NDIFF)
    if config.tests.verbosity <= 2:
        flags |= doctest.REPORT_ONLY_FIRST_FAILURE
    # Add all the doctests in all subpackages.
    doctest_files = {}
    for docsdir in packages:
        for filename in os.listdir(os.path.join('mailman', docsdir)):
            if os.path.splitext(filename)[1] == '.txt':
                doctest_files[filename] = os.path.join(docsdir, filename)
    # Sort or randomize the tests.
    if config.tests.randomize:
        files = doctest_files.keys()
        random.shuffle(files)
    else:
        files = sorted(doctest_files)
    for filename in files:
        path = doctest_files[filename]
        test = doctest.DocFileSuite(
            path,
            package='mailman',
            optionflags=flags,
            setUp=setup,
            tearDown=cleaning_teardown)
        suite.addTest(test)
    return suite