# Copyright (C) 2001-2007 by the Free Software Foundation, Inc.
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

"""Unit tests for the various Mailman/Handlers/*.py modules."""

import os
import sha
import time
import email
import errno
import cPickle
import unittest

from email.Generator import Generator

from Mailman import Errors
from Mailman import Message
from Mailman import Version
from Mailman import passwords
from Mailman.MailList import MailList
from Mailman.Queue.Switchboard import Switchboard
from Mailman.configuration import config
from Mailman.testing.base import TestBase

from Mailman.Handlers import Acknowledge
from Mailman.Handlers import AfterDelivery
from Mailman.Handlers import Approve
from Mailman.Handlers import CalcRecips
from Mailman.Handlers import Cleanse
from Mailman.Handlers import CookHeaders
from Mailman.Handlers import Decorate
from Mailman.Handlers import FileRecips
from Mailman.Handlers import Hold
from Mailman.Handlers import MimeDel
from Mailman.Handlers import Moderate
from Mailman.Handlers import Replybot
# Don't test handlers such as SMTPDirect and Sendmail here
from Mailman.Handlers import SpamDetect
from Mailman.Handlers import Tagger
from Mailman.Handlers import ToArchive
from Mailman.Handlers import ToDigest
from Mailman.Handlers import ToOutgoing
from Mailman.Handlers import ToUsenet



def password(cleartext):
    return passwords.make_secret(cleartext, passwords.Schemes.ssha)



class TestAcknowledge(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        # We're going to want to inspect this queue directory
        self._sb = Switchboard(config.VIRGINQUEUE_DIR)
        # Add a member
        self._mlist.addNewMember('aperson@example.org')
        self._mlist.personalize = False

    def tearDown(self):
        for f in os.listdir(config.VIRGINQUEUE_DIR):
            os.unlink(os.path.join(config.VIRGINQUEUE_DIR, f))
        TestBase.tearDown(self)

    def test_no_ack_msgdata(self):
        eq = self.assertEqual
        # Make sure there are no files in the virgin queue already
        eq(len(self._sb.files()), 0)
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        Acknowledge.process(self._mlist, msg,
                            {'original_sender': 'aperson@example.org'})
        eq(len(self._sb.files()), 0)

    def test_no_ack_not_a_member(self):
        eq = self.assertEqual
        # Make sure there are no files in the virgin queue already
        eq(len(self._sb.files()), 0)
        msg = email.message_from_string("""\
From: bperson@example.com

""", Message.Message)
        Acknowledge.process(self._mlist, msg,
                            {'original_sender': 'bperson@example.com'})
        eq(len(self._sb.files()), 0)

    def test_no_ack_sender(self):
        eq = self.assertEqual
        eq(len(self._sb.files()), 0)
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        Acknowledge.process(self._mlist, msg, {})
        eq(len(self._sb.files()), 0)

    def test_ack_no_subject(self):
        eq = self.assertEqual
        self._mlist.setMemberOption(
            'aperson@example.org', config.AcknowledgePosts, 1)
        eq(len(self._sb.files()), 0)
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        Acknowledge.process(self._mlist, msg, {})
        files = self._sb.files()
        eq(len(files), 1)
        qmsg, qdata = self._sb.dequeue(files[0])
        # Check the .db file
        eq(qdata.get('listname'), '_xtest@example.com')
        eq(qdata.get('recips'), ['aperson@example.org'])
        eq(qdata.get('version'), 3)
        # Check the .pck
        eq(str(qmsg['subject']), '_xtest post acknowledgement')
        eq(qmsg['to'], 'aperson@example.org')
        eq(qmsg['from'], '_xtest-bounces@example.com')
        eq(qmsg.get_content_type(), 'text/plain')
        eq(qmsg.get_param('charset'), 'us-ascii')
        msgid = qmsg['message-id']
        self.failUnless(msgid.startswith('<mailman.'))
        self.failUnless(msgid.endswith('._xtest@example.com>'))
        eq(qmsg.get_payload(), """\
Your message entitled

    (no subject)

was successfully received by the _xtest mailing list.

List info page: http://www.example.com/mailman/listinfo/_xtest@example.com
Your preferences: http://www.example.com/mailman/options/_xtest@example.com/aperson%40example.org
""")
        # Make sure we dequeued the only message
        eq(len(self._sb.files()), 0)

    def test_ack_with_subject(self):
        eq = self.assertEqual
        self._mlist.setMemberOption(
            'aperson@example.org', config.AcknowledgePosts, 1)
        eq(len(self._sb.files()), 0)
        msg = email.message_from_string("""\
From: aperson@example.org
Subject: Wish you were here

""", Message.Message)
        Acknowledge.process(self._mlist, msg, {})
        files = self._sb.files()
        eq(len(files), 1)
        qmsg, qdata = self._sb.dequeue(files[0])
        # Check the .db file
        eq(qdata.get('listname'), '_xtest@example.com')
        eq(qdata.get('recips'), ['aperson@example.org'])
        eq(qdata.get('version'), 3)
        # Check the .pck
        eq(str(qmsg['subject']), '_xtest post acknowledgement')
        eq(qmsg['to'], 'aperson@example.org')
        eq(qmsg['from'], '_xtest-bounces@example.com')
        eq(qmsg.get_content_type(), 'text/plain')
        eq(qmsg.get_param('charset'), 'us-ascii')
        msgid = qmsg['message-id']
        self.failUnless(msgid.startswith('<mailman.'))
        self.failUnless(msgid.endswith('._xtest@example.com>'))
        eq(qmsg.get_payload(), """\
Your message entitled

    Wish you were here

was successfully received by the _xtest mailing list.

List info page: http://www.example.com/mailman/listinfo/_xtest@example.com
Your preferences: http://www.example.com/mailman/options/_xtest@example.com/aperson%40example.org
""")
        # Make sure we dequeued the only message
        eq(len(self._sb.files()), 0)



class TestAfterDelivery(TestBase):
    # Both msg and msgdata are ignored
    def test_process(self):
        mlist = self._mlist
        last_post_time = mlist.last_post_time
        post_id = mlist.post_id
        AfterDelivery.process(mlist, None, None)
        self.failUnless(mlist.last_post_time > last_post_time)
        self.assertEqual(mlist.post_id, post_id + 1)



class TestApprove(TestBase):
    def test_short_circuit(self):
        msgdata = {'approved': 1}
        rtn = Approve.process(self._mlist, None, msgdata)
        # Not really a great test, but there's little else to assert
        self.assertEqual(rtn, None)

    def test_approved_moderator(self):
        mlist = self._mlist
        mlist.mod_password = password('wazoo')
        msg = email.message_from_string("""\
Approved: wazoo

""")
        msgdata = {}
        Approve.process(mlist, msg, msgdata)
        self.failUnless(msgdata.has_key('approved'))
        self.assertEqual(msgdata['approved'], 1)

    def test_approve_moderator(self):
        mlist = self._mlist
        mlist.mod_password = password('wazoo')
        msg = email.message_from_string("""\
Approve: wazoo

""")
        msgdata = {}
        Approve.process(mlist, msg, msgdata)
        self.failUnless(msgdata.has_key('approved'))
        self.assertEqual(msgdata['approved'], 1)

    def test_approved_admin(self):
        mlist = self._mlist
        mlist.password = password('wazoo')
        msg = email.message_from_string("""\
Approved: wazoo

""")
        msgdata = {}
        Approve.process(mlist, msg, msgdata)
        self.failUnless(msgdata.has_key('approved'))
        self.assertEqual(msgdata['approved'], 1)

    def test_approve_admin(self):
        mlist = self._mlist
        mlist.password = password('wazoo')
        msg = email.message_from_string("""\
Approve: wazoo

""")
        msgdata = {}
        Approve.process(mlist, msg, msgdata)
        self.failUnless(msgdata.has_key('approved'))
        self.assertEqual(msgdata['approved'], 1)

    def test_unapproved(self):
        mlist = self._mlist
        mlist.password = password('zoowa')
        msg = email.message_from_string("""\
Approve: wazoo

""")
        msgdata = {}
        Approve.process(mlist, msg, msgdata)
        self.assertEqual(msgdata.get('approved'), None)

    def test_trip_beentheres(self):
        mlist = self._mlist
        msg = email.message_from_string("""\
X-BeenThere: %s

""" % mlist.GetListEmail())
        self.assertRaises(Errors.LoopError, Approve.process, mlist, msg, {})



class TestCalcRecips(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        # Add a bunch of regular members
        mlist = self._mlist
        mlist.addNewMember('aperson@example.org')
        mlist.addNewMember('bperson@example.com')
        mlist.addNewMember('cperson@example.com')
        # And a bunch of digest members
        mlist.addNewMember('dperson@example.com', digest=1)
        mlist.addNewMember('eperson@example.com', digest=1)
        mlist.addNewMember('fperson@example.com', digest=1)

    def test_short_circuit(self):
        msgdata = {'recips': 1}
        rtn = CalcRecips.process(self._mlist, None, msgdata)
        # Not really a great test, but there's little else to assert
        self.assertEqual(rtn, None)

    def test_simple_path(self):
        msgdata = {}
        msg = email.message_from_string("""\
From: dperson@example.com

""", Message.Message)
        CalcRecips.process(self._mlist, msg, msgdata)
        self.failUnless(msgdata.has_key('recips'))
        recips = msgdata['recips']
        recips.sort()
        self.assertEqual(recips, ['aperson@example.org', 'bperson@example.com',
                                  'cperson@example.com'])

    def test_exclude_sender(self):
        msgdata = {}
        msg = email.message_from_string("""\
From: cperson@example.com

""", Message.Message)
        self._mlist.setMemberOption('cperson@example.com',
                                    config.DontReceiveOwnPosts, 1)
        CalcRecips.process(self._mlist, msg, msgdata)
        self.failUnless(msgdata.has_key('recips'))
        recips = msgdata['recips']
        recips.sort()
        self.assertEqual(recips, ['aperson@example.org', 'bperson@example.com'])

    def test_urgent_moderator(self):
        self._mlist.mod_password = password('xxXXxx')
        msgdata = {}
        msg = email.message_from_string("""\
From: dperson@example.com
Urgent: xxXXxx

""", Message.Message)
        CalcRecips.process(self._mlist, msg, msgdata)
        self.failUnless(msgdata.has_key('recips'))
        recips = msgdata['recips']
        recips.sort()
        self.assertEqual(recips, ['aperson@example.org', 'bperson@example.com',
                                  'cperson@example.com', 'dperson@example.com',
                                  'eperson@example.com', 'fperson@example.com'])

    def test_urgent_admin(self):
        self._mlist.mod_password = password('yyYYyy')
        self._mlist.password = password('xxXXxx')
        msgdata = {}
        msg = email.message_from_string("""\
From: dperson@example.com
Urgent: xxXXxx

""", Message.Message)
        CalcRecips.process(self._mlist, msg, msgdata)
        self.failUnless(msgdata.has_key('recips'))
        recips = msgdata['recips']
        recips.sort()
        self.assertEqual(recips, ['aperson@example.org', 'bperson@example.com',
                                  'cperson@example.com', 'dperson@example.com',
                                  'eperson@example.com', 'fperson@example.com'])

    def test_urgent_reject(self):
        self._mlist.mod_password = password('yyYYyy')
        self._mlist.password = password('xxXXxx')
        msgdata = {}
        msg = email.message_from_string("""\
From: dperson@example.com
Urgent: zzZZzz

""", Message.Message)
        self.assertRaises(Errors.RejectMessage,
                          CalcRecips.process,
                          self._mlist, msg, msgdata)

    # BAW: must test the do_topic_filters() path...



class TestCleanse(TestBase):
    def setUp(self):
        TestBase.setUp(self)

    def test_simple_cleanse(self):
        eq = self.assertEqual
        msg = email.message_from_string("""\
From: aperson@example.org
Approved: yes
Urgent: indeed
Reply-To: bperson@example.com
Sender: asystem@example.com
Return-Receipt-To: another@example.com
Disposition-Notification-To: athird@example.com
X-Confirm-Reading-To: afourth@example.com
X-PMRQC: afifth@example.com
Subject: a message to you

""", Message.Message)
        Cleanse.process(self._mlist, msg, {})
        eq(msg['approved'], None)
        eq(msg['urgent'], None)
        eq(msg['return-receipt-to'], None)
        eq(msg['disposition-notification-to'], None)
        eq(msg['x-confirm-reading-to'], None)
        eq(msg['x-pmrqc'], None)
        eq(msg['from'], 'aperson@example.org')
        eq(msg['reply-to'], 'bperson@example.com')
        eq(msg['sender'], 'asystem@example.com')
        eq(msg['subject'], 'a message to you')

    def test_anon_cleanse(self):
        eq = self.assertEqual
        msg = email.message_from_string("""\
From: aperson@example.org
Approved: yes
Urgent: indeed
Reply-To: bperson@example.com
Sender: asystem@example.com
Return-Receipt-To: another@example.com
Disposition-Notification-To: athird@example.com
X-Confirm-Reading-To: afourth@example.com
X-PMRQC: afifth@example.com
Subject: a message to you

""", Message.Message)
        self._mlist.anonymous_list = 1
        Cleanse.process(self._mlist, msg, {})
        eq(msg['approved'], None)
        eq(msg['urgent'], None)
        eq(msg['return-receipt-to'], None)
        eq(msg['disposition-notification-to'], None)
        eq(msg['x-confirm-reading-to'], None)
        eq(msg['x-pmrqc'], None)
        eq(len(msg.get_all('from')), 1)
        eq(len(msg.get_all('reply-to')), 1)
        eq(msg['from'], '_xtest@example.com')
        eq(msg['reply-to'], '_xtest@example.com')
        eq(msg['sender'], None)
        eq(msg['subject'], 'a message to you')



class TestCookHeaders(TestBase):
    def test_transform_noack_to_xack(self):
        eq = self.assertEqual
        msg = email.message_from_string("""\
X-Ack: yes

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {'noack': 1})
        eq(len(msg.get_all('x-ack')), 1)
        eq(msg['x-ack'], 'no')

    def test_original_sender(self):
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        msgdata = {}
        CookHeaders.process(self._mlist, msg, msgdata)
        self.assertEqual(msgdata.get('original_sender'), 'aperson@example.org')

    def test_no_original_sender(self):
        msg = email.message_from_string("""\
Subject: about this message

""", Message.Message)
        msgdata = {}
        CookHeaders.process(self._mlist, msg, msgdata)
        self.assertEqual(msgdata.get('original_sender'), '')

    def test_xbeenthere(self):
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {})
        self.assertEqual(msg['x-beenthere'], '_xtest@example.com')

    def test_multiple_xbeentheres(self):
        eq = self.assertEqual
        msg = email.message_from_string("""\
From: aperson@example.org
X-BeenThere: alist@another.example.com

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {})
        eq(len(msg.get_all('x-beenthere')), 2)
        beentheres = msg.get_all('x-beenthere')
        beentheres.sort()
        eq(beentheres, ['_xtest@example.com', 'alist@another.example.com'])

    def test_nonexisting_mmversion(self):
        eq = self.assertEqual
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {})
        eq(msg['x-mailman-version'], Version.VERSION)

    def test_existing_mmversion(self):
        eq = self.assertEqual
        msg = email.message_from_string("""\
From: aperson@example.org
X-Mailman-Version: 3000

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {})
        eq(len(msg.get_all('x-mailman-version')), 1)
        eq(msg['x-mailman-version'], '3000')

    def test_nonexisting_precedence(self):
        eq = self.assertEqual
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {})
        eq(msg['precedence'], 'list')

    def test_existing_precedence(self):
        eq = self.assertEqual
        msg = email.message_from_string("""\
From: aperson@example.org
Precedence: junk

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {})
        eq(len(msg.get_all('precedence')), 1)
        eq(msg['precedence'], 'junk')

    def test_subject_munging_no_subject(self):
        self._mlist.subject_prefix = '[XTEST] '
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        msgdata = {}
        CookHeaders.process(self._mlist, msg, msgdata)
        self.assertEqual(msgdata.get('origsubj'), '')
        self.assertEqual(str(msg['subject']), '[XTEST] (no subject)')

    def test_subject_munging(self):
        self._mlist.subject_prefix = '[XTEST] '
        msg = email.message_from_string("""\
From: aperson@example.org
Subject: About Mailman...

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {})
        self.assertEqual(msg['subject'], '[XTEST] About Mailman...')

    def test_no_subject_munging_for_digests(self):
        self._mlist.subject_prefix = '[XTEST] '
        msg = email.message_from_string("""\
From: aperson@example.org
Subject: About Mailman...

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {'isdigest': 1})
        self.assertEqual(msg['subject'], 'About Mailman...')

    def test_no_subject_munging_for_fasttrack(self):
        self._mlist.subject_prefix = '[XTEST] '
        msg = email.message_from_string("""\
From: aperson@example.org
Subject: About Mailman...

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {'_fasttrack': 1})
        self.assertEqual(msg['subject'], 'About Mailman...')

    def test_no_subject_munging_has_prefix(self):
        self._mlist.subject_prefix = '[XTEST] '
        msg = email.message_from_string("""\
From: aperson@example.org
Subject: Re: [XTEST] About Mailman...

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {})
        self.assertEqual(msg['subject'], 'Re: [XTEST] About Mailman...')

    def test_subject_munging_i18n(self):
        self._mlist.subject_prefix = '[XTEST]'
        msg = Message.Message()
        msg['Subject'] = '=?iso-2022-jp?b?GyRCJWEhPCVrJV4lcxsoQg==?='
        CookHeaders.process(self._mlist, msg, {})
        self.assertEqual(unicode(msg['subject']),
                         u'[XTEST] \u30e1\u30fc\u30eb\u30de\u30f3')
        self.assertEqual(msg['subject'],
                         '[XTEST] =?iso-2022-jp?b?GyRCJWEhPCVrJV4lcxsoQg==?=')
        self._mlist.subject_prefix = '[XTEST %d]'
        self._mlist.post_id = 456
        msg = Message.Message()
        msg['Subject'] = '=?iso-2022-jp?b?GyRCJWEhPCVrJV4lcxsoQg==?='
        CookHeaders.process(self._mlist, msg, {})
        self.assertEqual(unicode(msg['subject']),
                         u'[XTEST 456] \u30e1\u30fc\u30eb\u30de\u30f3')
        self.assertEqual(msg['subject'],
                     '[XTEST 456] =?iso-2022-jp?b?GyRCJWEhPCVrJV4lcxsoQg==?=')
        msg = Message.Message()
        msg['Subject'
             ] = 'Re: [XTEST 123] =?iso-2022-jp?b?GyRCJWEhPCVrJV4lcxsoQg==?='
        CookHeaders.process(self._mlist, msg, {})
        # next code suceeds if python email patch tracker #1681333 is applied.
        #self.assertEqual(unicode(msg['subject']),
        #             u'[XTEST 456] Re: \u30e1\u30fc\u30eb\u30de\u30f3')
        self.assertEqual(msg['subject'],
                 '[XTEST 456] Re: =?iso-2022-jp?b?GyRCJWEhPCVrJV4lcxsoQg==?=')

    def test_subject_munging_prefix_number(self):
        self._mlist.subject_prefix = '[XTEST %d]'
        self._mlist.post_id = 456
        msg = Message.Message()
        msg['Subject'] = 'About Mailman...'
        CookHeaders.process(self._mlist, msg, {})
        self.assertEqual(msg['subject'], '[XTEST 456] About Mailman...')
        msg = Message.Message()
        msg['Subject'] = 'Re: [XTEST 123] About Mailman...'
        CookHeaders.process(self._mlist, msg, {})
        self.assertEqual(msg['subject'], '[XTEST 456] Re: About Mailman...')

    def test_subject_munging_prefix_newstyle(self):
        self._mlist.subject_prefix = '[XTEST]'
        config.OLD_STYLE_PREFIXING = False
        msg = Message.Message()
        msg['Subject'] = 'Re: [XTEST] About Mailman...'
        CookHeaders.process(self._mlist, msg, {})
        self.assertEqual(msg['subject'], '[XTEST] Re: About Mailman...')

    def test_subject_munging_prefix_crooked(self):
        # In this test case, we get an extra space between the prefix and
        # the original subject.  It's because the original is crooked.
        # Note that isubject starting by '\n ' is generated by some version of
        # Eudora Japanese edition.
        self._mlist.subject_prefix = '[XTEST]'
        msg = Message.Message()
        msg['Subject'] = '\n About Mailman...'
        CookHeaders.process(self._mlist, msg, {})
        self.assertEqual(str(msg['subject']), '[XTEST]  About Mailman...')
        del msg['subject']
        msg['Subject'] = '\n =?iso-2022-jp?b?GyRCJWEhPCVrJV4lcxsoQg==?='
        CookHeaders.process(self._mlist, msg, {})
        self.assertEqual(str(msg['subject']), 
                     '[XTEST] =?iso-2022-jp?b?IBskQiVhITwlayVeJXMbKEI=?=')

    def test_reply_to_list(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.reply_goes_to_list = 1
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        CookHeaders.process(mlist, msg, {})
        eq(msg['reply-to'], '_xtest@example.com')
        eq(msg.get_all('reply-to'), ['_xtest@example.com'])

    def test_reply_to_list_with_strip(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.reply_goes_to_list = 1
        mlist.first_strip_reply_to = 1
        msg = email.message_from_string("""\
From: aperson@example.org
Reply-To: bperson@example.com

""", Message.Message)
        CookHeaders.process(mlist, msg, {})
        eq(msg['reply-to'], '_xtest@example.com')
        eq(msg.get_all('reply-to'), ['_xtest@example.com'])

    def test_reply_to_explicit(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.reply_goes_to_list = 2
        mlist.reply_to_address = 'mlist@example.com'
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        CookHeaders.process(mlist, msg, {})
        eq(msg['reply-to'], 'mlist@example.com')
        eq(msg.get_all('reply-to'), ['mlist@example.com'])

    def test_reply_to_explicit_with_strip(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.reply_goes_to_list = 2
        mlist.first_strip_reply_to = 1
        mlist.reply_to_address = 'mlist@example.com'
        msg = email.message_from_string("""\
From: aperson@example.org
Reply-To: bperson@example.com

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {})
        eq(msg['reply-to'], 'mlist@example.com')
        eq(msg.get_all('reply-to'), ['mlist@example.com'])

    def test_reply_to_extends_to_list(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.reply_goes_to_list = 1
        mlist.first_strip_reply_to = 0
        msg = email.message_from_string("""\
From: aperson@example.org
Reply-To: bperson@example.com

""", Message.Message)
        CookHeaders.process(mlist, msg, {})
        eq(msg['reply-to'], 'bperson@example.com, _xtest@example.com')

    def test_reply_to_extends_to_explicit(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.reply_goes_to_list = 2
        mlist.first_strip_reply_to = 0
        mlist.reply_to_address = 'mlist@example.com'
        msg = email.message_from_string("""\
From: aperson@example.org
Reply-To: bperson@example.com

""", Message.Message)
        CookHeaders.process(mlist, msg, {})
        eq(msg['reply-to'], 'mlist@example.com, bperson@example.com')

    def test_list_headers_nolist(self):
        eq = self.assertEqual
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {'_nolist': 1})
        eq(msg['list-id'], None)
        eq(msg['list-help'], None)
        eq(msg['list-unsubscribe'], None)
        eq(msg['list-subscribe'], None)
        eq(msg['list-post'], None)
        eq(msg['list-archive'], None)

    def test_list_headers(self):
        eq = self.assertEqual
        self._mlist.archive = 1
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        oldval = config.DEFAULT_URL_HOST
        config.DEFAULT_URL_HOST = 'www.example.com'
        try:
            CookHeaders.process(self._mlist, msg, {})
        finally:
            config.DEFAULT_URL_HOST = oldval
        eq(msg['list-id'], '<_xtest.example.com>')
        eq(msg['list-help'], '<mailto:_xtest-request@example.com?subject=help>')
        eq(msg['list-unsubscribe'],
           '<http://www.example.com/mailman/listinfo/_xtest@example.com>,'
           '\n\t<mailto:_xtest-request@example.com?subject=unsubscribe>')
        eq(msg['list-subscribe'],
           '<http://www.example.com/mailman/listinfo/_xtest@example.com>,'
           '\n\t<mailto:_xtest-request@example.com?subject=subscribe>')
        eq(msg['list-post'], '<mailto:_xtest@example.com>')
        eq(msg['list-archive'],
           '<http://www.example.com/pipermail/_xtest@example.com>')

    def test_list_headers_with_description(self):
        eq = self.assertEqual
        self._mlist.archive = 1
        self._mlist.description = 'A Test List'
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        CookHeaders.process(self._mlist, msg, {})
        eq(unicode(msg['list-id']), u'A Test List <_xtest.example.com>')
        eq(msg['list-help'], '<mailto:_xtest-request@example.com?subject=help>')
        eq(msg['list-unsubscribe'],
           '<http://www.example.com/mailman/listinfo/_xtest@example.com>,'
           '\n\t<mailto:_xtest-request@example.com?subject=unsubscribe>')
        eq(msg['list-subscribe'],
           '<http://www.example.com/mailman/listinfo/_xtest@example.com>,'
           '\n\t<mailto:_xtest-request@example.com?subject=subscribe>')
        eq(msg['list-post'], '<mailto:_xtest@example.com>')



class TestDecorate(TestBase):
    def test_short_circuit(self):
        msgdata = {'isdigest': 1}
        rtn = Decorate.process(self._mlist, None, msgdata)
        # Not really a great test, but there's little else to assert
        self.assertEqual(rtn, None)

    def test_no_multipart(self):
        mlist = self._mlist
        mlist.msg_header = 'header\n'
        mlist.msg_footer = 'footer'
        msg = email.message_from_string("""\
From: aperson@example.org

Here is a message.
""")
        Decorate.process(self._mlist, msg, {})
        self.assertEqual(msg.get_payload(), """\
header
Here is a message.
footer""")

    def test_no_multipart_template(self):
        mlist = self._mlist
        mlist.msg_header = '%(real_name)s header\n'
        mlist.msg_footer = '%(real_name)s footer'
        mlist.real_name = 'XTest'
        msg = email.message_from_string("""\
From: aperson@example.org

Here is a message.
""")
        Decorate.process(self._mlist, msg, {})
        self.assertEqual(msg.get_payload(), """\
XTest header
Here is a message.
XTest footer""")

    def test_no_multipart_type_error(self):
        mlist = self._mlist
        mlist.msg_header = '%(real_name) header\n'
        mlist.msg_footer = '%(real_name) footer'
        mlist.real_name = 'XTest'
        msg = email.message_from_string("""\
From: aperson@example.org

Here is a message.
""")
        Decorate.process(self._mlist, msg, {})
        self.assertEqual(msg.get_payload(), """\
%(real_name) header
Here is a message.
%(real_name) footer""")

    def test_no_multipart_value_error(self):
        mlist = self._mlist
        # These will generate warnings in logs/error
        mlist.msg_header = '%(real_name)p header\n'
        mlist.msg_footer = '%(real_name)p footer'
        mlist.real_name = 'XTest'
        msg = email.message_from_string("""\
From: aperson@example.org

Here is a message.
""")
        Decorate.process(self._mlist, msg, {})
        self.assertEqual(msg.get_payload(), """\
%(real_name)p header
Here is a message.
%(real_name)p footer""")

    def test_no_multipart_missing_key(self):
        mlist = self._mlist
        mlist.msg_header = '%(spooge)s header\n'
        mlist.msg_footer = '%(spooge)s footer'
        msg = email.message_from_string("""\
From: aperson@example.org

Here is a message.
""")
        Decorate.process(self._mlist, msg, {})
        self.assertEqual(msg.get_payload(), """\
%(spooge)s header
Here is a message.
%(spooge)s footer""")

    def test_multipart(self):
        eq = self.ndiffAssertEqual
        mlist = self._mlist
        mlist.msg_header = 'header'
        mlist.msg_footer = 'footer'
        msg1 = email.message_from_string("""\
From: aperson@example.org

Here is the first message.
""")
        msg2 = email.message_from_string("""\
From: bperson@example.com

Here is the second message.
""")
        msg = Message.Message()
        msg.set_type('multipart/mixed')
        msg.set_boundary('BOUNDARY')
        msg.attach(msg1)
        msg.attach(msg2)
        Decorate.process(self._mlist, msg, {})
        eq(msg.as_string(unixfrom=0), """\
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="BOUNDARY"

--BOUNDARY
Content-Type: text/plain; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: inline

header
--BOUNDARY
From: aperson@example.org

Here is the first message.

--BOUNDARY
From: bperson@example.com

Here is the second message.

--BOUNDARY
Content-Type: text/plain; charset="us-ascii"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Content-Disposition: inline

footer
--BOUNDARY--""")

    def test_image(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.msg_header = 'header\n'
        mlist.msg_footer = 'footer'
        msg = email.message_from_string("""\
From: aperson@example.org
Content-type: image/x-spooge

IMAGEDATAIMAGEDATAIMAGEDATA
""")
        Decorate.process(self._mlist, msg, {})
        eq(len(msg.get_payload()), 3)
        self.assertEqual(msg.get_payload(1).get_payload(), """\
IMAGEDATAIMAGEDATAIMAGEDATA
""")

    def test_personalize_assert(self):
        raises = self.assertRaises
        raises(AssertionError, Decorate.process,
               self._mlist, None, {'personalize': 1})
        raises(AssertionError, Decorate.process,
               self._mlist, None, {'personalize': 1,
                                   'recips': [1, 2, 3]})

    def test_no_multipart_mixed_charset(self):
        mlist = self._mlist
        mlist.preferred_language = 'ja'
        mlist.msg_header = '%(description)s header'
        mlist.msg_footer = '%(description)s footer'
        mlist.description = u'\u65e5\u672c\u8a9e'
        msg = Message.Message()
        msg.set_payload('Fran\xe7aise', 'iso-8859-1')
        Decorate.process(self._mlist, msg, {})
        self.assertEqual(msg.as_string(unixfrom=0), """\
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"
Content-Transfer-Encoding: base64

5pel5pys6KqeIGhlYWRlcgpGcmFuw6dhaXNlCuaXpeacrOiqniBmb290ZXI=
""")



class TestFileRecips(TestBase):
    def test_short_circuit(self):
        msgdata = {'recips': 1}
        rtn = FileRecips.process(self._mlist, None, msgdata)
        # Not really a great test, but there's little else to assert
        self.assertEqual(rtn, None)

    def test_file_nonexistant(self):
        msgdata = {}
        FileRecips.process(self._mlist, None, msgdata)
        self.assertEqual(msgdata.get('recips'), [])

    def test_file_exists_no_sender(self):
        msg = email.message_from_string("""\
To: yall@example.com

""", Message.Message)
        msgdata = {}
        file = os.path.join(self._mlist.fullpath(), 'members.txt')
        addrs = ['aperson@example.org', 'bperson@example.com',
                 'cperson@example.com', 'dperson@example.com']
        fp = open(file, 'w')
        try:
            for addr in addrs:
                print >> fp, addr
            fp.close()
            FileRecips.process(self._mlist, msg, msgdata)
            self.assertEqual(msgdata.get('recips'), addrs)
        finally:
            try:
                os.unlink(file)
            except OSError, e:
                if e.errno <> e.ENOENT: raise

    def test_file_exists_no_member(self):
        msg = email.message_from_string("""\
From: eperson@example.com
To: yall@example.com

""", Message.Message)
        msgdata = {}
        file = os.path.join(self._mlist.fullpath(), 'members.txt')
        addrs = ['aperson@example.org', 'bperson@example.com',
                 'cperson@example.com', 'dperson@example.com']
        fp = open(file, 'w')
        try:
            for addr in addrs:
                print >> fp, addr
            fp.close()
            FileRecips.process(self._mlist, msg, msgdata)
            self.assertEqual(msgdata.get('recips'), addrs)
        finally:
            try:
                os.unlink(file)
            except OSError, e:
                if e.errno <> e.ENOENT: raise

    def test_file_exists_is_member(self):
        msg = email.message_from_string("""\
From: aperson@example.org
To: yall@example.com

""", Message.Message)
        msgdata = {}
        file = os.path.join(self._mlist.fullpath(), 'members.txt')
        addrs = ['aperson@example.org', 'bperson@example.com',
                 'cperson@example.com', 'dperson@example.com']
        fp = open(file, 'w')
        try:
            for addr in addrs:
                print >> fp, addr
                self._mlist.addNewMember(addr)
            fp.close()
            FileRecips.process(self._mlist, msg, msgdata)
            self.assertEqual(msgdata.get('recips'), addrs[1:])
        finally:
            try:
                os.unlink(file)
            except OSError, e:
                if e.errno <> e.ENOENT: raise



class TestHold(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        self._mlist.administrivia = 1
        self._mlist.respond_to_post_requests = 0
        self._mlist.admin_immed_notify = 0
        # We're going to want to inspect this queue directory
        self._sb = Switchboard(config.VIRGINQUEUE_DIR)

    def tearDown(self):
        for f in os.listdir(config.VIRGINQUEUE_DIR):
            os.unlink(os.path.join(config.VIRGINQUEUE_DIR, f))
        TestBase.tearDown(self)
        try:
            os.unlink(os.path.join(config.DATA_DIR, 'pending.db'))
        except OSError, e:
            if e.errno <> errno.ENOENT: raise
        for f in [holdfile for holdfile in os.listdir(config.DATA_DIR)
                  if holdfile.startswith('heldmsg-')]:
            os.unlink(os.path.join(config.DATA_DIR, f))

    def test_short_circuit(self):
        msgdata = {'approved': 1}
        rtn = Hold.process(self._mlist, None, msgdata)
        # Not really a great test, but there's little else to assert
        self.assertEqual(rtn, None)

    def test_administrivia(self):
        msg = email.message_from_string("""\
From: aperson@example.org
Subject: unsubscribe

""", Message.Message)
        self.assertRaises(Hold.Administrivia, Hold.process,
                          self._mlist, msg, {})

    def test_max_recips(self):
        self._mlist.max_num_recipients = 5
        msg = email.message_from_string("""\
From: aperson@example.org
To: _xtest@example.com, bperson@example.com
Cc: cperson@example.com
Cc: dperson@example.com (Jimmy D. Person)
To: Billy E. Person <eperson@example.com>

Hey folks!
""", Message.Message)
        self.assertRaises(Hold.TooManyRecipients, Hold.process,
                          self._mlist, msg, {})

    def test_implicit_destination(self):
        self._mlist.require_explicit_destination = 1
        msg = email.message_from_string("""\
From: aperson@example.org
Subject: An implicit message

""", Message.Message)
        self.assertRaises(Hold.ImplicitDestination, Hold.process,
                          self._mlist, msg, {})

    def test_implicit_destination_fromusenet(self):
        self._mlist.require_explicit_destination = 1
        msg = email.message_from_string("""\
From: aperson@example.org
Subject: An implicit message

""", Message.Message)
        rtn = Hold.process(self._mlist, msg, {'fromusenet': 1})
        self.assertEqual(rtn, None)

    def test_suspicious_header(self):
        self._mlist.bounce_matching_headers = 'From: .*person@(blah.)?example.org'
        msg = email.message_from_string("""\
From: aperson@example.org
To: _xtest@example.net
Subject: An implicit message

""", Message.Message)
        self.assertRaises(Hold.SuspiciousHeaders, Hold.process,
                          self._mlist, msg, {})

    def test_suspicious_header_ok(self):
        self._mlist.bounce_matching_headers = 'From: .*person@blah.example.com'
        msg = email.message_from_string("""\
From: aperson@example.org
To: _xtest@example.com
Subject: An implicit message

""", Message.Message)
        rtn = Hold.process(self._mlist, msg, {})
        self.assertEqual(rtn, None)

    def test_max_message_size(self):
        self._mlist.max_message_size = 1
        msg = email.message_from_string("""\
From: aperson@example.org
To: _xtest@example.com

xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
""", Message.Message)
        self.assertRaises(Hold.MessageTooBig, Hold.process,
                          self._mlist, msg, {})

    def test_hold_notifications(self):
        eq = self.assertEqual
        self._mlist.respond_to_post_requests = 1
        self._mlist.admin_immed_notify = 1
        # Now cause an implicit destination hold
        msg = email.message_from_string("""\
From: aperson@example.org

""", Message.Message)
        self.assertRaises(Hold.ImplicitDestination, Hold.process,
                          self._mlist, msg, {})
        # Now we have to make sure there are two messages in the virgin queue,
        # one to the sender and one to the list owners.
        qfiles = {}
        files = self._sb.files()
        eq(len(files), 2)
        for filebase in files:
            qmsg, qdata = self._sb.dequeue(filebase)
            to = qmsg['to']
            qfiles[to] = qmsg, qdata
        # BAW: We could be testing many other attributes of either the
        # messages or the metadata files...
        keys = qfiles.keys()
        keys.sort()
        eq(keys, ['_xtest-owner@example.com', 'aperson@example.org'])
        # Get the pending cookie from the message to the sender
        pmsg, pdata = qfiles['aperson@example.org']
        confirmlines = pmsg.get_payload().split('\n')
        cookie = confirmlines[-3].split('/')[-1]
        # We also need to make sure there's an entry in the Pending database
        # for the hold message.
        data = self._mlist.pend_confirm(cookie)
        eq(data, ('H', 1))
        heldmsg = os.path.join(config.DATA_DIR, 'heldmsg-_xtest-1.pck')
        self.failUnless(os.path.exists(heldmsg))
        os.unlink(heldmsg)
        holdfiles = [f for f in os.listdir(config.DATA_DIR)
                     if f.startswith('heldmsg-')]
        eq(len(holdfiles), 0)



class TestMimeDel(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        self._mlist.filter_content = 1
        self._mlist.filter_mime_types = ['image/jpeg']
        self._mlist.pass_mime_types = []
        self._mlist.convert_html_to_plaintext = 1

    def test_outer_matches(self):
        msg = email.message_from_string("""\
From: aperson@example.org
Content-Type: image/jpeg
MIME-Version: 1.0

xxxxx
""")
        self.assertRaises(Errors.DiscardMessage, MimeDel.process,
                          self._mlist, msg, {})

    def test_strain_multipart(self):
        eq = self.assertEqual
        msg = email.message_from_string("""\
From: aperson@example.org
Content-Type: multipart/mixed; boundary=BOUNDARY
MIME-Version: 1.0

--BOUNDARY
Content-Type: image/jpeg
MIME-Version: 1.0

xxx

--BOUNDARY
Content-Type: image/gif
MIME-Version: 1.0

yyy
--BOUNDARY--
""")
        MimeDel.process(self._mlist, msg, {})
        eq(len(msg.get_payload()), 1)
        subpart = msg.get_payload(0)
        eq(subpart.get_content_type(), 'image/gif')
        eq(subpart.get_payload(), 'yyy')

    def test_collapse_multipart_alternative(self):
        eq = self.assertEqual
        msg = email.message_from_string("""\
From: aperson@example.org
Content-Type: multipart/mixed; boundary=BOUNDARY
MIME-Version: 1.0

--BOUNDARY
Content-Type: multipart/alternative; boundary=BOUND2
MIME-Version: 1.0

--BOUND2
Content-Type: image/jpeg
MIME-Version: 1.0

xxx

--BOUND2
Content-Type: image/gif
MIME-Version: 1.0

yyy
--BOUND2--

--BOUNDARY--
""")
        MimeDel.process(self._mlist, msg, {})
        eq(len(msg.get_payload()), 1)
        eq(msg.get_content_type(), 'multipart/mixed')
        subpart = msg.get_payload(0)
        eq(subpart.get_content_type(), 'image/gif')
        eq(subpart.get_payload(), 'yyy')

    def test_convert_to_plaintext(self):
        eq = self.assertEqual
        # XXX Skip this test if the html->text converter program is not
        # available.
        program = config.HTML_TO_PLAIN_TEXT_COMMAND.split()[0]
        if os.path.isfile(program):
            msg = email.message_from_string("""\
From: aperson@example.org
Content-Type: text/html
MIME-Version: 1.0

<html><head></head>
<body></body></html>
""")
            MimeDel.process(self._mlist, msg, {})
            eq(msg.get_content_type(), 'text/plain')
            eq(msg.get_payload(), '\n\n\n')

    def test_deep_structure(self):
        eq = self.assertEqual
        self._mlist.filter_mime_types.append('text/html')
        msg = email.message_from_string("""\
From: aperson@example.org
Content-Type: multipart/mixed; boundary=AAA

--AAA
Content-Type: multipart/mixed; boundary=BBB

--BBB
Content-Type: image/jpeg

xxx
--BBB
Content-Type: image/jpeg

yyy
--BBB---
--AAA
Content-Type: multipart/alternative; boundary=CCC

--CCC
Content-Type: text/html

<h2>This is a header</h2>

--CCC
Content-Type: text/plain

A different message
--CCC--
--AAA
Content-Type: image/gif

zzz
--AAA
Content-Type: image/gif

aaa
--AAA--
""")
        MimeDel.process(self._mlist, msg, {})
        payload = msg.get_payload()
        eq(len(payload), 3)
        part1 = msg.get_payload(0)
        eq(part1.get_content_type(), 'text/plain')
        eq(part1.get_payload(), 'A different message')
        part2 = msg.get_payload(1)
        eq(part2.get_content_type(), 'image/gif')
        eq(part2.get_payload(), 'zzz')
        part3 = msg.get_payload(2)
        eq(part3.get_content_type(), 'image/gif')
        eq(part3.get_payload(), 'aaa')

    def test_top_multipart_alternative(self):
        eq = self.assertEqual
        self._mlist.filter_mime_types.append('text/html')
        msg = email.message_from_string("""\
From: aperson@example.org
Content-Type: multipart/alternative; boundary=AAA

--AAA
Content-Type: text/html

<b>This is some html</b>
--AAA
Content-Type: text/plain

This is plain text
--AAA--
""")
        MimeDel.process(self._mlist, msg, {})
        eq(msg.get_content_type(), 'text/plain')
        eq(msg.get_payload(), 'This is plain text')



class TestModerate(TestBase):
    pass



class TestReplybot(TestBase):
    pass



class TestSpamDetect(TestBase):
    def test_short_circuit(self):
        msgdata = {'approved': 1}
        rtn = SpamDetect.process(self._mlist, None, msgdata)
        # Not really a great test, but there's little else to assert
        self.assertEqual(rtn, None)

    def test_spam_detect(self):
        msg1 = email.message_from_string("""\
From: aperson@example.org

A message.
""")
        msg2 = email.message_from_string("""\
To: xlist@example.com

A message.
""")
        spammers = config.KNOWN_SPAMMERS[:]
        try:
            config.KNOWN_SPAMMERS.append(('from', '.?person'))
            self.assertRaises(SpamDetect.SpamDetected,
                              SpamDetect.process, self._mlist, msg1, {})
            rtn = SpamDetect.process(self._mlist, msg2, {})
            self.assertEqual(rtn, None)
        finally:
            config.KNOWN_SPAMMERS = spammers



class TestTagger(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        self._mlist.topics = [('bar fight', '.*bar.*', 'catch any bars', 1)]
        self._mlist.topics_enabled = 1

    def test_short_circuit(self):
        self._mlist.topics_enabled = 0
        rtn = Tagger.process(self._mlist, None, {})
        # Not really a great test, but there's little else to assert
        self.assertEqual(rtn, None)

    def test_simple(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.topics_bodylines_limit = 0
        msg = email.message_from_string("""\
Subject: foobar
Keywords: barbaz

""")
        msgdata = {}
        Tagger.process(mlist, msg, msgdata)
        eq(msg['x-topics'], 'bar fight')
        eq(msgdata.get('topichits'), ['bar fight'])

    def test_all_body_lines_plain_text(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.topics_bodylines_limit = -1
        msg = email.message_from_string("""\
Subject: Was
Keywords: Raw

Subject: farbaw
Keywords: barbaz
""")
        msgdata = {}
        Tagger.process(mlist, msg, msgdata)
        eq(msg['x-topics'], 'bar fight')
        eq(msgdata.get('topichits'), ['bar fight'])

    def test_no_body_lines(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.topics_bodylines_limit = 0
        msg = email.message_from_string("""\
Subject: Was
Keywords: Raw

Subject: farbaw
Keywords: barbaz
""")
        msgdata = {}
        Tagger.process(mlist, msg, msgdata)
        eq(msg['x-topics'], None)
        eq(msgdata.get('topichits'), None)

    def test_body_lines_in_multipart(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.topics_bodylines_limit = -1
        msg = email.message_from_string("""\
Subject: Was
Keywords: Raw
Content-Type: multipart/alternative; boundary="BOUNDARY"

--BOUNDARY
From: sabo
To: obas

Subject: farbaw
Keywords: barbaz

--BOUNDARY--
""")
        msgdata = {}
        Tagger.process(mlist, msg, msgdata)
        eq(msg['x-topics'], 'bar fight')
        eq(msgdata.get('topichits'), ['bar fight'])

    def test_body_lines_no_part(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.topics_bodylines_limit = -1
        msg = email.message_from_string("""\
Subject: Was
Keywords: Raw
Content-Type: multipart/alternative; boundary=BOUNDARY

--BOUNDARY
From: sabo
To: obas
Content-Type: message/rfc822

Subject: farbaw
Keywords: barbaz

--BOUNDARY
From: sabo
To: obas
Content-Type: message/rfc822

Subject: farbaw
Keywords: barbaz

--BOUNDARY--
""")
        msgdata = {}
        Tagger.process(mlist, msg, msgdata)
        eq(msg['x-topics'], None)
        eq(msgdata.get('topichits'), None)



class TestToArchive(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        # We're going to want to inspect this queue directory
        self._sb = Switchboard(config.ARCHQUEUE_DIR)

    def tearDown(self):
        for f in os.listdir(config.ARCHQUEUE_DIR):
            os.unlink(os.path.join(config.ARCHQUEUE_DIR, f))
        TestBase.tearDown(self)

    def test_short_circuit(self):
        eq = self.assertEqual
        msgdata = {'isdigest': 1}
        ToArchive.process(self._mlist, None, msgdata)
        eq(len(self._sb.files()), 0)
        # Try the other half of the or...
        self._mlist.archive = 0
        ToArchive.process(self._mlist, None, msgdata)
        eq(len(self._sb.files()), 0)
        # Now try the various message header shortcuts
        msg = email.message_from_string("""\
X-No-Archive: YES

""")
        self._mlist.archive = 1
        ToArchive.process(self._mlist, msg, {})
        eq(len(self._sb.files()), 0)
        # And for backwards compatibility
        msg = email.message_from_string("""\
X-Archive: NO

""")
        ToArchive.process(self._mlist, msg, {})
        eq(len(self._sb.files()), 0)

    def test_normal_archiving(self):
        eq = self.assertEqual
        msg = email.message_from_string("""\
Subject: About Mailman

It rocks!
""")
        ToArchive.process(self._mlist, msg, {})
        files = self._sb.files()
        eq(len(files), 1)
        msg2, data = self._sb.dequeue(files[0])
        eq(len(data), 3)
        eq(data['version'], 3)
        # Clock skew makes this unreliable
        #self.failUnless(data['received_time'] <= time.time())
        eq(msg.as_string(unixfrom=0), msg2.as_string(unixfrom=0))



class TestToDigest(TestBase):
    def _makemsg(self, i=0):
        msg = email.message_from_string("""From: aperson@example.org
To: _xtest@example.com
Subject: message number %(i)d

Here is message %(i)d
""" % {'i' : i})
        return msg

    def setUp(self):
        TestBase.setUp(self)
        self._path = os.path.join(self._mlist.fullpath(), 'digest.mbox')
        fp = open(self._path, 'w')
        g = Generator(fp)
        for i in range(5):
            g.flatten(self._makemsg(i), unixfrom=1)
        fp.close()
        self._sb = Switchboard(config.VIRGINQUEUE_DIR)

    def tearDown(self):
        try:
            os.unlink(self._path)
        except OSError, e:
            if e.errno <> errno.ENOENT: raise
        for f in os.listdir(config.VIRGINQUEUE_DIR):
            os.unlink(os.path.join(config.VIRGINQUEUE_DIR, f))
        TestBase.tearDown(self)

    def test_short_circuit(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.digestable = 0
        eq(ToDigest.process(mlist, None, {}), None)
        mlist.digestable = 1
        eq(ToDigest.process(mlist, None, {'isdigest': 1}), None)
        eq(self._sb.files(), [])

    def test_undersized(self):
        msg = self._makemsg(99)
        size = os.path.getsize(self._path) + len(str(msg))
        self._mlist.digest_size_threshhold = (size + 1) * 1024
        ToDigest.process(self._mlist, msg, {})
        self.assertEqual(self._sb.files(), [])

    def test_send_a_digest(self):
        eq = self.assertEqual
        mlist = self._mlist
        msg = self._makemsg(99)
        size = os.path.getsize(self._path) + len(str(msg))
        mlist.digest_size_threshhold = 0
        ToDigest.process(mlist, msg, {})
        files = self._sb.files()
        # There should be two files in the queue, one for the MIME digest and
        # one for the RFC 1153 digest.
        eq(len(files), 2)
        # Now figure out which of the two files is the MIME digest and which
        # is the RFC 1153 digest.
        for filebase in files:
            qmsg, qdata = self._sb.dequeue(filebase)
            if qmsg.get_content_maintype() == 'multipart':
                mimemsg = qmsg
                mimedata = qdata
            else:
                rfc1153msg = qmsg
                rfc1153data = qdata
        eq(rfc1153msg.get_content_type(), 'text/plain')
        eq(mimemsg.get_content_type(), 'multipart/mixed')
        eq(mimemsg['from'], mlist.GetRequestEmail())
        eq(mimemsg['subject'],
           '%(realname)s Digest, Vol %(volume)d, Issue %(issue)d' % {
            'realname': mlist.real_name,
            'volume'  : mlist.volume,
            'issue'   : mlist.next_digest_number - 1,
            })
        eq(mimemsg['to'], mlist.GetListEmail())
        # BAW: this test is incomplete...


    def test_send_i18n_digest(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.preferred_language = 'fr'
        msg = email.message_from_string("""\
From: aperson@example.org
To: _xtest@example.com
Subject: =?iso-2022-jp?b?GyRCMGxIVhsoQg==?=
MIME-Version: 1.0
Content-Type: text/plain; charset=iso-2022-jp
Content-Transfer-Encoding: 7bit

\x1b$B0lHV\x1b(B
""")
        mlist.digest_size_threshhold = 0
        ToDigest.process(mlist, msg, {})
        files = self._sb.files()
        eq(len(files), 2)
        for filebase in files:
            qmsg, qdata = self._sb.dequeue(filebase)
            if qmsg.get_content_maintype() == 'multipart':
                mimemsg = qmsg
                mimedata = qdata
            else:
                rfc1153msg = qmsg
                rfc1153data = qdata
        eq(rfc1153msg.get_content_type(), 'text/plain')
        eq(rfc1153msg.get_content_charset(), 'utf-8')
        eq(rfc1153msg['content-transfer-encoding'], 'base64')
        toc = mimemsg.get_payload()[1]
        eq(toc.get_content_type(), 'text/plain')
        eq(toc.get_content_charset(), 'utf-8')
        eq(toc['content-transfer-encoding'], 'base64')



class TestToOutgoing(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        # We're going to want to inspect this queue directory
        self._sb = Switchboard(config.OUTQUEUE_DIR)
        # Save and set this value
        self._interval = config.VERP_DELIVERY_INTERVAL
        config.VERP_DELIVERY_INTERVAL = 1

    def tearDown(self):
        # Restore this value
        config.VERP_DELIVERY_INTERVAL = self._interval
        for f in os.listdir(config.OUTQUEUE_DIR):
            os.unlink(os.path.join(config.OUTQUEUE_DIR, f))
        TestBase.tearDown(self)

    def test_outgoing(self):
        eq = self.assertEqual
        msg = email.message_from_string("""\
Subject: About Mailman

It rocks!
""")
        msgdata = {'foo': 1, 'bar': 2}
        ToOutgoing.process(self._mlist, msg, msgdata)
        files = self._sb.files()
        eq(len(files), 1)
        msg2, data = self._sb.dequeue(files[0])
        eq(msg.as_string(unixfrom=0), msg2.as_string(unixfrom=0))
        eq(len(data), 7)
        eq(data['foo'], 1)
        eq(data['bar'], 2)
        eq(data['version'], 3)
        eq(data['listname'], '_xtest@example.com')
        eq(data['verp'], 1)
        # Clock skew makes this unreliable
        #self.failUnless(data['received_time'] <= time.time())



class TestToUsenet(TestBase):
    def setUp(self):
        TestBase.setUp(self)
        # We're going to want to inspect this queue directory
        self._sb = Switchboard(config.NEWSQUEUE_DIR)

    def tearDown(self):
        for f in os.listdir(config.NEWSQUEUE_DIR):
            os.unlink(os.path.join(config.NEWSQUEUE_DIR, f))
        TestBase.tearDown(self)

    def test_short_circuit(self):
        eq = self.assertEqual
        mlist = self._mlist
        mlist.gateway_to_news = 0
        ToUsenet.process(mlist, None, {})
        eq(len(self._sb.files()), 0)
        mlist.gateway_to_news = 1
        ToUsenet.process(mlist, None, {'isdigest': 1})
        eq(len(self._sb.files()), 0)
        ToUsenet.process(mlist, None, {'fromusenet': 1})
        eq(len(self._sb.files()), 0)

    def test_to_usenet(self):
        # BAW: Should we, can we, test the error conditions that only log to a
        # file instead of raising an exception?
        eq = self.assertEqual
        mlist = self._mlist
        mlist.gateway_to_news = 1
        mlist.linked_newsgroup = 'foo'
        mlist.nntp_host = 'bar'
        msg = email.message_from_string("""\
Subject: About Mailman

Mailman rocks!
""")
        ToUsenet.process(mlist, msg, {})
        files = self._sb.files()
        eq(len(files), 1)
        msg2, data = self._sb.dequeue(files[0])
        eq(msg.as_string(unixfrom=0), msg2.as_string(unixfrom=0))
        eq(data['version'], 3)
        eq(data['listname'], '_xtest@example.com')
        # Clock skew makes this unreliable
        #self.failUnless(data['received_time'] <= time.time())



def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestAcknowledge))
    suite.addTest(unittest.makeSuite(TestAfterDelivery))
    suite.addTest(unittest.makeSuite(TestApprove))
    suite.addTest(unittest.makeSuite(TestCalcRecips))
    suite.addTest(unittest.makeSuite(TestCleanse))
    suite.addTest(unittest.makeSuite(TestCookHeaders))
    suite.addTest(unittest.makeSuite(TestDecorate))
    suite.addTest(unittest.makeSuite(TestFileRecips))
    suite.addTest(unittest.makeSuite(TestHold))
    suite.addTest(unittest.makeSuite(TestMimeDel))
    suite.addTest(unittest.makeSuite(TestModerate))
    suite.addTest(unittest.makeSuite(TestReplybot))
    suite.addTest(unittest.makeSuite(TestSpamDetect))
    suite.addTest(unittest.makeSuite(TestTagger))
    suite.addTest(unittest.makeSuite(TestToArchive))
    suite.addTest(unittest.makeSuite(TestToDigest))
    suite.addTest(unittest.makeSuite(TestToOutgoing))
    suite.addTest(unittest.makeSuite(TestToUsenet))
    return suite
