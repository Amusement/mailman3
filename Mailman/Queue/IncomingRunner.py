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

"""Incoming queue runner."""

# A typical Mailman list exposes four aliases which point to three different
# wrapped scripts.  E.g. for a list named `mylist', you'd have:
#
# mylist         -> post
# mylist-admin   -> mailowner
# mylist-request -> mailcmd
# mylist-owner   -> mailowner (through an alias to mylist-admin)
#
# Only 3 scripts are used for historical purposes, but some MTAs have more
# direct ways to shuttle messages into the Mailman incoming queues.
#
# mylist-request is a robot address; its sole purpose is to process emailed
# commands in a Majordomo-like fashion.  mylist-admin is supposed to reach the
# list owners, but it performs one vital step before list owner delivery - it
# examines the message for bounce content.  mylist-owner is the fallback for
# delivery to the list owners; it performs no bounce detection, but it /does/
# look for bounce loops, which can occur if a list owner address is bouncing.
#
# So delivery flow of messages look like this:
#
# joerandom ---> mylist ---> list members
#    |                           |
#    |                           |[bounces]
#    +-------> mylist-admin <----+ <-------------------------------+
#    |              |                                              |
#    |              +--->[internal bounce processing]              |
#    |                               |                             |
#    |                               |    [bounce found]           |
#    |                               +--->[register and discard]   |
#    |                               |                             |
#    |                               |     [no bounce found]       |
#    |                               +---> list owners <------+    |
#    |                                          |             |    |
#    |                                          |[bounces]    |    |
#    +-------> mylist-owner <-------------------+             |    |
#    |              |                                         |    |
#    |              |     [bounce loop detected]              |    |
#    |              +---> [log and discard]                   |    |
#    |              |                                         |    |
#    |              +-----------------------------------------+    |
#    |               [no bounce loop detected]                     |
#    |                                                             |
#    |                                                             |
#    +-------> mylist-request                                      |
#                   |                                              |
#                   +---> [command processor]                      |
#                                 |                                |
#                                 +---> joerandom                  |
#                                           |                      |
#                                           |[bounces]             |
#                                           +----------------------+
#
# With Mailman 2.1 we're splitting the normal incoming mail from the
# owner/admin/request mail because we'd like to be able to tune each queue
# separately.  The IncomingRunner handles only mail sent to the list, which
# ends up in qfiles/in


import sys
import os

from Mailman import mm_cfg
from Mailman import Errors
from Mailman import LockFile
from Mailman.Queue.Runner import Runner
from Mailman.Logging.Syslog import syslog
from Mailman.pythonlib.StringIO import StringIO



class IncomingRunner(Runner):
    def __init__(self, slice=None, numslices=1, cachelists=1):
        Runner.__init__(self, mm_cfg.INQUEUE_DIR,
                        slice, numslices, cachelists)

    def _dispose(self, mlist, msg, msgdata):
        # Try to get the list lock.
        try:
            mlist.Lock(timeout=mm_cfg.LIST_LOCK_TIMEOUT)
        except LockFile.TimeOutError:
            # Oh well, try again later
            return 1
        #
        # Process the message through a handler pipeline.  The handler
        # pipeline can actually come from one of three places: the message
        # metadata, the mlist, or the global pipeline.
        #
        # If a message was requeued due to an uncaught exception, its metadata
        # will contain the retry pipeline.  Use this above all else.
        # Otherwise, if the mlist has a `pipeline' attribute, it should be
        # used.  Final fallback is the global pipeline.
        try:
            pipeline = self._get_pipeline(mlist, msg, msgdata)
            return self._dopipeline(mlist, msg, msgdata, pipeline)
        finally:
            mlist.Save()
            mlist.Unlock()

    # Overridable
    def _get_pipeline(self, mlist, msg, msgdata):
        # We must return a copy of the list, otherwise, the first message that
        # flows through the pipeline will empty it out!
        return msgdata.get('pipeline',
                           getattr(mlist, 'pipeline',
                                   mm_cfg.GLOBAL_PIPELINE))[:]

    def _dopipeline(self, mlist, msg, msgdata, pipeline):
        while pipeline:
            handler = pipeline.pop(0)
            modname = 'Mailman.Handlers.' + handler
            mod = __import__(modname)
            func = getattr(sys.modules[modname], 'process')
            try:
                pid = os.getpid()
                func(mlist, msg, msgdata)
                # Failsafe -- a child may have leaked through.
                if pid <> os.getpid():
                    syslog('error', 'child process leaked through: %s' %
                           modname)
                    os._exit(1)
            except Errors.DiscardMessage:
                # Throw the message away; we need do nothing else with it.
                return 0
            except Errors.MessageHeld:
                # Let the approval process take it from here.  The message no
                # longer needs to be queued.
                return 0
            except Exception, e:
                # Some other exception occurred, which we definitely did not
                # expect, so set this message up for requeuing.
                self._log(e)
                # We stick the name of the failed module back into the front
                # of the pipeline list so that it can resume where it left off
                # when qrunner tries to redeliver it.
                pipeline.insert(0, handler)
                return 1
        # We've successfully completed handling of this message
        return 0
