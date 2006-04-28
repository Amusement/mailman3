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
import shutil
import optparse

from Mailman import MailList
from Mailman import Utils
from Mailman import mm_cfg
from Mailman.i18n import _

__i18n_templates__ = True



def remove_it(listname, filename, msg):
    if os.path.islink(filename):
        print _('Removing $msg')
        os.unlink(filename)
    elif os.path.isdir(filename):
        print _('Removing $msg')
        shutil.rmtree(filename)
    elif os.path.isfile(filename):
        os.unlink(filename)
    else:
        print _('$listname $msg not found as $filename')



def parseargs():
    parser = optparse.OptionParser(version=mm_cfg.MAILMAN_VERSION,
                                   usage=_("""\
%%prog [options] listname

Remove the components of a mailing list with impunity - beware!

This removes (almost) all traces of a mailing list.  By default, the lists
archives are not removed, which is very handy for retiring old lists.
"""))
    parser.add_option('-a', '--archives',
                      default=False, action='store_true', help=_("""\
Remove the list's archives too, or if the list has already been deleted,
remove any residual archives."""))
    opts, args = parser.parse_args()
    if not args:
        parser.print_help()
        print >> sys.stderr, _('Missing listname')
        sys.exit(1)
    if len(args) > 1:
        parser.print_help()
        print >> sys.stderr, _('Unexpected arguments')
        sys.exit(1)
    return parser, opts, args



def main():
    parser, opts, args = parseargs()
    listname = args[0].lower().strip()
    if not Utils.list_exists(listname):
        if not opts.archives:
            print >> sys.stderr, _(
                'No such list (or list already deleted): $listname')
            sys.exit(1)
        else:
            print _(
                'No such list: $listname.  Removing its residual archives.')

    if not opts.archives:
        print _('Not removing archives.  Reinvoke with -a to remove them.')

    removeables = []
    if Utils.list_exists(listname):
        mlist = MailList.MailList(listname, lock=False)
        # Do the MTA-specific list deletion tasks
        if mm_cfg.MTA:
            modname = 'Mailman.MTA.' + mm_cfg.MTA
            __import__(modname)
            sys.modules[modname].remove(mlist)

        removeables.append((os.path.join('lists', listname), _('list info')))

    # Remove any stale locks associated with the list
    for filename in os.listdir(mm_cfg.LOCK_DIR):
        fn_listname = filename.split('.')[0]
        if fn_listname == listname:
            removeables.append((os.path.join(mm_cfg.LOCK_DIR, filename),
                                _('stale lock file')))

    if opts.archives:
        removeables.extend([
            (os.path.join('archives', 'private', listname),
             _('private archives')),
            (os.path.join('archives', 'private', listname + '.mbox'),
             _('private archives')),
            (os.path.join('archives', 'public', listname),
             _('public archives')),
            (os.path.join('archives', 'public', listname + '.mbox'),
             _('public archives')),
            ])

    for dirtmpl, msg in removeables:
        path = os.path.join(mm_cfg.VAR_PREFIX, dirtmpl)
        remove_it(listname, path, msg)



if __name__ == '__main__':
    main()
