# Copyright (C) 1998-2006 by the Free Software Foundation, Inc.
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

import os
import sys
import errno
import shutil
import optparse

from Mailman import Errors
from Mailman import i18n
from Mailman import mm_cfg
from Mailman.Archiver.HyperArch import HyperArchive
from Mailman.LockFile import LockFile
from Mailman.MailList import MailList

_ = i18n._
i18n.set_language(mm_cfg.DEFAULT_SERVER_LANGUAGE)

__i18n_templates__ = True



def parseargs():
    parser = optparse.OptionParser(version=mm_cfg.MAILMAN_VERSION,
                                   usage=_("""\
%%prog [options] listname [mbox]

Rebuild a list's archive.

Use this command to rebuild the archives for a mailing list.  You may want to
do this if you edit some messages in an archive, or remove some messages from
an archive.

Where 'mbox' is the path to a list's complete mbox archive.  Usually this will
be some path in the archives/private directory.  For example:

% bin/arch mylist archives/private/mylist.mbox/mylist.mbox

'mbox' is optional.  If it is missing, it is calculated from the listname.
"""))
    parser.add_option('-q', '--quiet',
                      dest='verbose', default=True, action='store_false',
                      help=_('Make the archiver output less verbose'))
    parser.add_option('--wipe',
                      default=False, action='store_true',
                      help=_("""\
First wipe out the original archive before regenerating.  You usually want to
specify this argument unless you're generating the archive in chunks."""))
    parser.add_option('-s', '--start',
                      default=None, type='int', metavar='N',
                      help=_("""\
Start indexing at article N, where article 0 is the first in the mbox.
Defaults to 0."""))
    parser.add_option('-e', '--end',
                      default=None, type='int', metavar='M',
                      help=_("""\
End indexing at article M.  This script is not very efficient with respect to
memory management, and for large archives, it may not be possible to index the
mbox entirely.  For that reason, you can specify the start and end article
numbers."""))
    opts, args = parser.parse_args()
    if len(args) < 1:
        parser.print_help()
        print >> sys.stderr, _('listname is required')
        sys.exit(1)
    if len(args) > 2:
        parser.print_help()
        print >> sys.stderr, _('Unexpected arguments')
        sys.exit(1)
    return parser, opts, args



def main():
    parser, opts, args = parseargs()

    listname = args[0].lower().strip()
    if len(args) < 2:
        mbox = None
    else:
        mbox = args[1]

    # Open the mailing list object
    mlist = None
    lock = None
    try:
        try:
            mlist = MailList(listname)
        except Errors.MMListError, e:
            parser.print_help()
            print >> sys.stderr, _('No such list: $listname\n$e')
            sys.exit(1)
        if mbox is None:
            mbox = mlist.ArchiveFileName()

        i18n.set_language(mlist.preferred_language)
        # Lay claim to the archive's lock file.  This is so no other post can
        # mess up the archive while we're processing it.  Try to pick a
        # suitably long period of time for the lock lifetime even though we
        # really don't know how long it will take.
        #
        # XXX processUnixMailbox() should refresh the lock.
        #
        # XXX This may not be necessary because I think we lay claim to the
        # list lock up above, although that may be too short to be of use (and
        # maybe we don't really want to lock the list anyway).
        lockfile = os.path.join(mm_cfg.LOCK_DIR, mlist._internal_name) + \
                   '.archiver.lock'
        # set the lock lifetime to 3 hours.  XXX is this reasonable???
        lock = LockFile(lockfile, lifetime=3*60*60)
        lock.lock()
        # Maybe wipe the old archives
        if opts.wipe:
            if mlist.scrub_nondigest:
                # TK: save the attachments dir because they are not in mbox
                saved = False
                atchdir = os.path.join(mlist.archive_dir(), 'attachments')
                savedir = os.path.join(mlist.archive_dir() + '.mbox',
                                       'attachments')
                try:
                    os.rename(atchdir, savedir)
                    saved = True
                except OSError, e:
                    if e.errno <> errno.ENOENT:
                        raise
            shutil.rmtree(mlist.archive_dir())
            if mlist.scrub_nondigest and saved:
                os.renames(savedir, atchdir)
        try:
            fp = open(mbox)
        except IOError, e:
            if e.errno == errno.ENOENT:
                print >> sys.stderr, _('Cannot open mbox file: $mbox')
            else:
                print >> sys.stderr, e
            sys.exit(1)

        archiver = HyperArchive(mlist)
        archiver.VERBOSE = opts.verbose
        try:
            archiver.processUnixMailbox(fp, opts.start, opts.end)
        finally:
            archiver.close()
        fp.close()
    finally:
        if lock:
            lock.unlock()
        if mlist:
            mlist.Unlock()



if __name__ == '__main__':
    main()
