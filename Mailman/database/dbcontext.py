# Copyright (C) 2006 by the Free Software Foundation, Inc.
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

import weakref

from sqlalchemy import *
from string import Template

from Mailman import Version
from Mailman.configuration import config
from Mailman.database import address
from Mailman.database import listdata
from Mailman.database import version
from Mailman.database.txnsupport import txn



class MlistRef(weakref.ref):
    def __init__(self, mlist, callback):
        super(MlistRef, self).__init__(mlist, callback)
        self.fqdn_listname = mlist.fqdn_listname



class DBContext(object):
    def __init__(self):
        self.tables = {}
        self.metadata = None
        self.session = None
        # Special transaction used only for MailList.Lock() .Save() and
        # .Unlock() interface.
        self._mlist_txns = {}

    def connect(self):
        # Calculate the engine url
        url = Template(config.SQLALCHEMY_ENGINE_URL).safe_substitute(
            config.paths)
        self.metadata = BoundMetaData(url)
        self.metadata.engine.echo = config.SQLALCHEMY_ECHO
        # Create all the table objects, and then let SA conditionally create
        # them if they don't yet exist.
        version_table = None
        for module in (address, listdata, version):
            table = module.make_table(self.metadata)
            self.tables[table.name] = table
            if module is version:
                version_table = table
        self.metadata.create_all()
        # Validate schema version, updating if necessary (XXX)
        from Mailman.interact import interact
        r = version_table.select(version_table.c.component=='schema').execute()
        row = r.fetchone()
        if row is None:
            # Database has not yet been initialized
            version_table.insert().execute(
                component='schema',
                version=Version.DATABASE_SCHEMA_VERSION)
        elif row.version <> Version.DATABASE_SCHEMA_VERSION:
            # XXX Update schema
            raise SchemaVersionMismatchError(row.version)
        self.session = create_session()

    # Cooperative method for use with @txn decorator
    def _withtxn(self, meth, *args, **kws):
        try:
            txn = self.session.create_transaction()
            rtn = meth(*args, **kws)
        except:
            txn.rollback()
            raise
        else:
            txn.commit()
            return rtn

    def _unlock_mref(self, mref):
        txn = self._mlist_txns.pop(mref.fqdn_listname, None)
        if txn is not None:
            txn.rollback()

    # Higher level interface
    def api_lock(self, mlist):
        # Don't try to re-lock a list
        if mlist.fqdn_listname in self._mlist_txns:
            return
        txn = self.session.create_transaction()
        mref = MlistRef(mlist, self._unlock_mref)
        self._mlist_txns[mlist.fqdn_listname] = txn

    def api_unlock(self, mlist):
        txn = self._mlist_txns.pop(mlist.fqdn_listname, None)
        if txn is not None:
            txn.rollback()

    def api_save(self, mlist):
        # When dealing with MailLists, .Save() will always be followed by
        # .Unlock().  However lists can also be unlocked without saving.  But
        # if it's been locked it will always be unlocked.  So the rollback in
        # unlock will essentially be no-op'd if we've already saved the list.
        txn = self._mlist_txns.pop(mlist.fqdn_listname, None)
        if txn is not None:
            txn.commit()

    @txn
    def api_add_list(self, mlist):
        self.session.save(mlist)

    @txn
    def api_remove_list(self, mlist):
        self.session.delete(mlist)

    @txn
    def api_find_list(self, listname, hostname):
        from Mailman.MailList import MailList
        q = self.session.query(MailList)
        mlists = q.select_by(list_name=listname, host_name=hostname)
        assert len(mlists) <= 1, 'Duplicate mailing lists!'
        if mlists:
            return mlists[0]
        return None

    @txn
    def api_get_list_names(self):
        table = self.tables['Listdata']
        results = table.select().execute()
        return [(row[table.c.list_name], row[table.c.host_name])
                for row in results.fetchall()]



dbcontext = DBContext()
