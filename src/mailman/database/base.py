# Copyright (C) 2006-2014 by the Free Software Foundation, Inc.
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

from __future__ import absolute_import, print_function, unicode_literals

__metaclass__ = type
__all__ = [
    'StormBaseDatabase',
    ]


import os
import sys
import logging

from lazr.config import as_boolean
from pkg_resources import resource_listdir, resource_string
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from zope.interface import implementer

from mailman.config import config
from mailman.interfaces.database import IDatabase
from mailman.model.version import Version
from mailman.utilities.string import expand

log = logging.getLogger('mailman.config')

NL = '\n'



@implementer(IDatabase)
class SABaseDatabase:
    """The database base class for use with SQLAlchemy.

    Use this as a base class for your DB-Specific derived classes.
    """
    # Tag used to distinguish the database being used.  Override this in base
    # classes.

    TAG = ''

    def __init__(self):
        self.url = None
        self.store = None
        self.transaction = None

    def begin(self):
        """See `IDatabase`."""
        # SA does this for us.
        pass

    def commit(self):
        """See `IDatabase`."""
        self.store.commit()

    def abort(self):
        """See `IDatabase`."""
        self.store.rollback()

    def _database_exists(self):
        """Return True if the database exists and is initialized.

        Return False when Mailman needs to create and initialize the
        underlying database schema.

        Base classes *must* override this.
        """
        raise NotImplementedError

    def _pre_reset(self, store):
        """Clean up method for testing.

        This method is called during the test suite just before all the model
        tables are removed.  Override this to perform any database-specific
        pre-removal cleanup.
        """
        pass

    def _post_reset(self, store):
        """Clean up method for testing.

        This method is called during the test suite just after all the model
        tables have been removed.  Override this to perform any
        database-specific post-removal cleanup.
        """
        pass

    def initialize(self, debug=None):
        """See `IDatabase`"""
        # Calculate the engine url
        url = expand(config.database.url, config.paths)
        log.debug('Database url: %s', url)
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
        self.url = url
        self.engine = create_engine(url)
        session = sessionmaker(bind=self.engine)
        self.store = session()
        self.store.commit()

    def load_migrations(self, until=None):
        """Load schema migrations.

        :param until: Load only the migrations up to the specified timestamp.
            With default value of None, load all migrations.
        :type until: string
        """
        from mailman.database.model import Model
        Model.metadata.create_all(self.engine)

    def load_sql(self, store, sql):
        """Load the given SQL into the store.

        :param store: The Storm store to load the schema into.
        :type store: storm.locals.Store`
        :param sql: The possibly multi-line SQL to load.
        :type sql: string
        """
        # Discard all blank and comment lines.
        lines = (line for line in sql.splitlines()
                 if line.strip() != '' and line.strip()[:2] != '--')
        sql = NL.join(lines)
        for statement in sql.split(';'):
            if statement.strip() != '':
                store.execute(statement + ';')


    @staticmethod
    def _make_temporary():
        raise NotImplementedError
