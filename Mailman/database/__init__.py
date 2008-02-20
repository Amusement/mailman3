# Copyright (C) 2006-2008 by the Free Software Foundation, Inc.
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

from __future__ import with_statement

__metaclass__ = type
__all__ = [
    'StockDatabase',
    ]

import os
import Mailman.Version

from locknix.lockfile import Lock
from storm.locals import create_database, Store
from string import Template
from urlparse import urlparse
from zope.interface import implements

from Mailman.configuration import config
from Mailman.database.listmanager import ListManager
from Mailman.database.messagestore import MessageStore
from Mailman.database.pending import Pendings
from Mailman.database.requests import Requests
from Mailman.database.usermanager import UserManager
from Mailman.database.version import Version
from Mailman.interfaces import IDatabase, SchemaVersionMismatchError



class StockDatabase:
    implements(IDatabase)

    def __init__(self):
        self.list_manager = None
        self.user_manager = None
        self.message_store = None
        self.pendings = None
        self.requests = None
        self._store = None

    def initialize(self, debug=None):
        # Serialize this so we don't get multiple processes trying to create
        # the database at the same time.
        with Lock(os.path.join(config.LOCK_DIR, 'dbcreate.lck')):
            self._create(debug)
        self.list_manager = ListManager()
        self.user_manager = UserManager()
        self.message_store = MessageStore()
        self.pendings = Pendings()
        self.requests = Requests()

    def _create(self, debug):
        # Calculate the engine url.
        url = Template(config.DEFAULT_DATABASE_URL).safe_substitute(
            config.paths)
        # XXX By design of SQLite, database file creation does not honor
        # umask.  See their ticket #1193:
        # http://www.sqlite.org/cvstrac/tktview?tn=1193,31
        #
        # This sucks for us because the mailman.db file /must/ be group
        # writable, however even though we guarantee our umask is 002 here, it
        # still gets created without the necessary g+w permission, due to
        # SQLite's policy.  This should only affect SQLite engines because its
        # the only one that creates a little file on the local file system.
        # This kludges around their bug by "touch"ing the database file before
        # SQLite has any chance to create it, thus honoring the umask and
        # ensuring the right permissions.  We only try to do this for SQLite
        # engines, and yes, we could have chmod'd the file after the fact, but
        # half dozen and all...
        touch(url)
        database = create_database(url)
        store = Store(database)
        database.DEBUG = (config.DEFAULT_DATABASE_ECHO
                          if debug is None else debug)
        # Storm does not currently have schema creation.  This is not an ideal
        # way to handle creating the database, but it's cheap and easy for
        # now.
        import Mailman.database
        schema_file = os.path.join(
            os.path.dirname(Mailman.database.__file__),
            'mailman.sql')
        with open(schema_file) as fp:
            sql = fp.read()
        for statement in sql.split(';'):
            store.execute(statement + ';')
        # Validate schema version.
        v = store.find(Version, component=u'schema').one()
        if not v:
            # Database has not yet been initialized
            v = Version(component=u'schema',
                        version=Mailman.Version.DATABASE_SCHEMA_VERSION)
            store.add(v)
        elif v.version <> Mailman.Version.DATABASE_SCHEMA_VERSION:
            # XXX Update schema
            raise SchemaVersionMismatchError(v.version)
        self.store = store

    def _reset(self):
        from Mailman.database.model import ModelMeta
        ModelMeta._reset(self.store)



def touch(url):
    parts = urlparse(url)
    if parts.scheme <> 'sqlite':
        return
    path = os.path.normpath(parts.path)
    fd = os.open(path, os.O_WRONLY |  os.O_NONBLOCK | os.O_CREAT, 0666)
    # Ignore errors
    if fd > 0:
        os.close(fd)
