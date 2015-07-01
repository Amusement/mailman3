# Copyright (C) 2007-2015 by the Free Software Foundation, Inc.
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

"""Model for users."""

__all__ = [
    'DomainOwner',
    'User',
    ]


from mailman.database.model import Model
from mailman.database.transaction import dbconnection
from mailman.database.types import UUID
from mailman.interfaces.address import (
    AddressAlreadyLinkedError, AddressNotLinkedError)
from mailman.interfaces.user import (
    IUser, PasswordChangeEvent, UnverifiedAddressError)
from mailman.model.address import Address
from mailman.model.preferences import Preferences
from mailman.model.roster import Memberships
from mailman.utilities.datetime import factory as date_factory
from mailman.utilities.uid import UniqueIDFactory
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Unicode
from sqlalchemy.orm import relationship, backref
from zope.event import notify
from zope.interface import implementer


uid_factory = UniqueIDFactory(context='users')



@implementer(IUser)
class User(Model):
    """Mailman users."""

    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    display_name = Column(Unicode)
     _essay = Column('essay', Unicode)
    _password = Column('password', Unicode)
    _user_id = Column(UUID, index=True)
    _created_on = Column(DateTime)
    is_server_owner = Column(Boolean, default=False)

    addresses = relationship(
        'Address', backref='user',
        primaryjoin=(id==Address.user_id))

    _preferred_address_id = Column(
        Integer,
        ForeignKey('address.id', use_alter=True,
                   name='_preferred_address',
                   ondelete='SET NULL'))

    _preferred_address = relationship(
        'Address', primaryjoin=(_preferred_address_id==Address.id),
        post_update=True)

    preferences_id = Column(Integer, ForeignKey('preferences.id'), index=True)
    preferences = relationship(
        'Preferences', backref=backref('user', uselist=False))

    @dbconnection
    def __init__(self, store, essay, display_name=None, preferences=None):
        super(User, self).__init__()
        self._created_on = date_factory.now()
        user_id = uid_factory.new_uid()
        assert store.query(User).filter_by(_user_id=user_id).count() == 0, (
            'Duplicate user id {0}'.format(user_id))
        self._user_id = user_id
        self.essay = essay
        self.display_name = ('' if display_name is None else display_name)
        if preferences is not None:
            store.add(preferences)
            self.preferences = preferences
        store.add(self)

    def __repr__(self):
        short_user_id = self.user_id.int
        return '<User "{0.display_name}" ({2}) at {1:#x}>'.format(
            self, id(self), short_user_id)

    @property
    def user_id(self):
        """See `IUser`."""
        return self._user_id

    @property
    def created_on(self):
        """See `IUser`."""
        return self._created_on
    @property
    def essay(self):
        return self._essay

    @essay.setter
    def essay(self, new_essay):
        self._essay = new_essay
        
    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, new_password):
        self._password = new_password
        notify(PasswordChangeEvent(self))

    def link(self, address):
        """See `IUser`."""
        if address.user is not None:
            raise AddressAlreadyLinkedError(address)
        address.user = self

    def unlink(self, address):
        """See `IUser`."""
        if address.user is None or address.user is not self:
            raise AddressNotLinkedError(address)
        address.user = None

    @property
    def preferred_address(self):
        """See `IUser`."""
        return self._preferred_address

    @preferred_address.setter
    def preferred_address(self, address):
        """See `IUser`."""
        if address.verified_on is None:
            raise UnverifiedAddressError(address)
        if self.controls(address.email):
            # This user already controls the email address.
            pass
        elif address.user is None:
            self.link(address)
        elif address.user != self:
            raise AddressAlreadyLinkedError(address)
        self._preferred_address = address

    @preferred_address.deleter
    def preferred_address(self):
        """See `IUser`."""
        self._preferred_address = None

    @dbconnection
    def controls(self, store, email):
        """See `IUser`."""
        found = store.query(Address).filter_by(email=email)
        if found.count() == 0:
            return False
        assert found.count() == 1, 'Unexpected count'
        return found[0].user is self

    @dbconnection
    def register(self, store, email, display_name=None):
        """See `IUser`."""
        # First, see if the address already exists
        address = store.query(Address).filter_by(email=email).first()
        if address is None:
            if display_name is None:
                display_name = ''
            address = Address(email=email, display_name=display_name)
            address.preferences = Preferences()
        # Link the address to the user if it is not already linked.
        if address.user is not None:
            raise AddressAlreadyLinkedError(address)
        address.user = self
        return address

    @property
    def memberships(self):
        return Memberships(self)



class DomainOwner(Model):
    """Internal table for associating domains to their owners."""

    __tablename__ = 'domain_owner'

    user_id = Column(Integer, ForeignKey('user.id'), primary_key=True)
    domain_id = Column(Integer, ForeignKey('domain.id'), primary_key=True)
