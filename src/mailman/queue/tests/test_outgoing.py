# Copyright (C) 2011 by the Free Software Foundation, Inc.
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

"""Test the outgoing queue runner."""

from __future__ import absolute_import, unicode_literals

__metaclass__ = type
__all__ = [
    'test_suite',
    ]


import unittest

from contextlib import contextmanager
from datetime import timedelta

from mailman.app.lifecycle import create_list
from mailman.config import config
from mailman.interfaces.mailinglist import Personalization
from mailman.queue.outgoing import OutgoingRunner
from mailman.testing.helpers import (
    get_queue_messages,
    make_testable_runner,
    specialized_message_from_string as message_from_string)
from mailman.testing.layers import ConfigLayer, SMTPLayer
from mailman.utilities.datetime import now



def run_once(qrunner):
    """Predicate for make_testable_runner().

    Ensures that the queue runner only runs once.
    """
    return True


@contextmanager
def temporary_config(name, settings):
    """Temporarily set a configuration (use in a with-statement)."""
    config.push(name, settings)
    try:
        yield
    finally:
        config.pop(name)



class TestOnce(unittest.TestCase):
    """Test outgoing runner message disposition."""

    layer = SMTPLayer

    def setUp(self):
        self._mlist = create_list('test@example.com')
        self._outq = config.switchboards['out']
        self._runner = make_testable_runner(OutgoingRunner, 'out', run_once)
        self._msg = message_from_string("""\
From: anne@example.com
To: test@example.com
Message-Id: <first>

""")
        self._msgdata = {}

    def test_deliver_after(self):
        # When the metadata has a deliver_after key in the future, the queue
        # runner will re-enqueue the message rather than delivering it.
        deliver_after = now() + timedelta(days=10)
        self._msgdata['deliver_after'] = deliver_after
        self._outq.enqueue(self._msg, self._msgdata,
                           tolist=True, listname='test@example.com')
        self._runner.run()
        items = get_queue_messages('out')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].msgdata['deliver_after'], deliver_after)
        self.assertEqual(items[0].msg['message-id'], '<first>')



captured_mlist = None
captured_msg = None
captured_msgdata = None

def capture(mlist, msg, msgdata):
    global captured_mlist, captured_msg, captured_msgdata
    captured_mlist = mlist
    captured_msg = msg
    captured_msgdata = msgdata


class TestVERPSettings(unittest.TestCase):
    """Test the selection of VERP based on various criteria."""

    layer = ConfigLayer

    def setUp(self):
        global captured_mlist, captured_msg, captured_msgdata
        # Push a config where actual delivery is handled by a dummy function.
        # We generally don't care what this does, since we're just testing the
        # setting of the 'verp' key in the metadata.
        config.push('fake outgoing', """
        [mta]
        outgoing: mailman.queue.tests.test_outgoing.capture
        """)
        # Reset the captured data.
        captured_mlist = None
        captured_msg = None
        captured_msgdata = None
        self._mlist = create_list('test@example.com')
        self._outq = config.switchboards['out']
        self._runner = make_testable_runner(OutgoingRunner, 'out')
        self._msg = message_from_string("""\
From: anne@example.com
To: test@example.com
Message-Id: <first>

""")

    def tearDown(self):
        config.pop('fake outgoing')

    def test_delivery_callback(self):
        # Test that the configuration variable calls the appropriate callback.
        self._outq.enqueue(self._msg, {}, listname='test@example.com')
        self._runner.run()
        self.assertEqual(captured_mlist, self._mlist)
        self.assertEqual(captured_msg.as_string(), self._msg.as_string())
        # Of course, the message metadata will contain a bunch of keys added
        # by the processing.  We don't really care about the details, so this
        # test is a good enough stand-in.
        self.assertEqual(captured_msgdata['listname'], 'test@example.com')

    def test_verp_in_metadata(self):
        # Test that if the metadata has a 'verp' key, it is unchanged.
        marker = 'yepper'
        msgdata = dict(verp=marker)
        self._outq.enqueue(self._msg, msgdata, listname='test@example.com')
        self._runner.run()
        self.assertEqual(captured_msgdata['verp'], marker)

    def test_personalized_deliveries_verp(self):
        # When deliveries are personalized, and the configuration setting
        # indicates, messages will be VERP'd.
        msgdata = {}
        self._mlist.personalize = Personalization.individual
        self._outq.enqueue(self._msg, msgdata, listname='test@example.com')
        with temporary_config('personalize', """
        [mta]
        verp_personalized_deliveries: yes
        """):
            self._runner.run()
        ## self.assertTrue(msgdata['verp'])
        msgdata = {}
        self._mlist.personalize = Personalization.full
        self._outq.enqueue(self._msg, msgdata, listname='test@example.com')
        with temporary_config('personalize', """
        [mta]
        verp_personalized_deliveries: yes
        """):
            self._runner.run()
        ## self.assertTrue(msgdata['verp'])



def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestOnce))
    suite.addTest(unittest.makeSuite(TestVERPSettings))
    return suite
