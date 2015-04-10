# Copyright (C) 2009-2015 by the Free Software Foundation, Inc.
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

"""Handle subscriptions."""

__all__ = [
    'SubscriptionService',
    'SubscriptionWorkflow',
    'handle_ListDeletingEvent',
    ]



from mailman.app.membership import add_member, delete_member
from mailman.app.moderator import hold_subscription
from mailman.app.workflow import Workflow
from mailman.core.constants import system_preferences
from mailman.database.transaction import dbconnection
from mailman.interfaces.address import IAddress
from mailman.interfaces.listmanager import (
    IListManager, ListDeletingEvent, NoSuchListError)
from mailman.interfaces.mailinglist import SubscriptionPolicy
from mailman.interfaces.member import DeliveryMode, MemberRole
from mailman.interfaces.subscriptions import (
    ISubscriptionService, MissingUserError, RequestRecord)
from mailman.interfaces.user import IUser
from mailman.interfaces.usermanager import IUserManager
from mailman.model.member import Member
from mailman.utilities.datetime import now
from operator import attrgetter
from sqlalchemy import and_, or_
from uuid import UUID
from zope.component import getUtility
from zope.interface import implementer



def _membership_sort_key(member):
    """Sort function for find_members().

    The members are sorted first by unique list id, then by subscribed email
    address, then by role.
    """
    return (member.list_id, member.address.email, member.role.value)



class SubscriptionWorkflow(Workflow):
    """Workflow of a subscription request."""

    INITIAL_STATE = 'sanity_checks'
    SAVE_ATTRIBUTES = (
        'pre_approved',
        'pre_confirmed',
        'pre_verified',
        )

    def __init__(self, mlist, subscriber, *,
                 pre_verified=False, pre_confirmed=False, pre_approved=False):
        super().__init__()
        self.mlist = mlist
        # The subscriber must be either an IUser or IAddress.
        if IAddress.providedBy(subscriber):
            self.address = subscriber
            self.user = self.address.user
        elif IUser.providedBy(subscriber):
            self.address = subscriber.preferred_address
            self.user = subscriber
        else:
            raise AssertionError('subscriber is neither an IUser nor IAddress')
        self.subscriber = subscriber
        self.pre_verified = pre_verified
        self.pre_confirmed = pre_confirmed
        self.pre_approved = pre_approved

    def _step_sanity_checks(self):
        # Ensure that we have both an address and a user, even if the address
        # is not verified.  We can't set the preferred address until it is
        # verified.
        if self.user is None:
            # The address has no linked user so create one, link it, and set
            # the user's preferred address.
            assert self.address is not None, 'No address or user'
            self.user = getUtility(IUserManager).make_user(self.address.email)
        if self.address is None:
            assert self.user.preferred_address is None, (
                "Preferred address exists, but wasn't used in constructor")
            addresses = list(self.user.addresses)
            if len(addresses) == 0:
                raise AssertionError('User has no addresses: {}'.format(
                    self.user))
            # This is rather arbitrary, but we have no choice.
            self.address = addresses[0]
        assert self.user is not None and self.address is not None, (
            'Insane sanity check results')
        self.push('verification_checks')

    def _step_verification_checks(self):
        # Is the address already verified, or is the pre-verified flag set?
        if self.address.verified_on is None:
            if self.pre_verified:
                self.address.verified_on = now()
            else:
                # The address being subscribed is not yet verified, so we need
                # to send a validation email that will also confirm that the
                # user wants to be subscribed to this mailing list.
                self.push('send_confirmation')
                return
        self.push('confirmation_checks')

    def _step_confirmation_checks(self):
        # If the list's subscription policy is open, then the user can be
        # subscribed right here and now.
        if self.mlist.subscription_policy is SubscriptionPolicy.open:
            self.push('do_subscription')
            return
        # If we do not need the user's confirmation, then skip to the
        # moderation checks.
        if self.mlist.subscription_policy is SubscriptionPolicy.moderate:
            self.push('moderation_checks')
            return
        # If the subscription has been pre-confirmed, then we can skip to the
        # moderation checks.
        if self.pre_confirmed:
            self.push('moderation_checks')
            return
        # The user must confirm their subscription.
        self.push('send_confirmation')

    def _step_moderation_checks(self):
        # Does the moderator need to approve the subscription request?
        assert self.mlist.subscription_policy in (
            SubscriptionPolicy.moderate,
            SubscriptionPolicy.confirm_then_moderate)
        if self.pre_approved:
            self.push('do_subscription')
        else:
            self.push('get_moderator_approval')

    def _step_do_subscription(self):
        # We can immediately subscribe the user to the mailing list.
        self.mlist.subscribe(self.subscriber)

    def _step_get_moderator_approval(self):
        # In order to get the moderator's approval, we need to hold the
        # subscription request in the database
        request = RequestRecord(
            self.address.email, self.subscriber.display_name,
            DeliveryMode.regular, 'en')
        hold_subscription(self.mlist, request)

    def _step_send_confirmation(self):
        self._next.append('moderation_check')
        self.save()
        self._next.clear() # stop iteration until we get confirmation
        # XXX: create the Pendable, send the ConfirmationNeededEvent
        # (see Registrar.register)


@implementer(ISubscriptionService)
class SubscriptionService:
    """Subscription services for the REST API."""

    __name__ = 'members'

    def get_members(self):
        """See `ISubscriptionService`."""
        # {list_id -> {role -> [members]}}
        by_list = {}
        user_manager = getUtility(IUserManager)
        for member in user_manager.members:
            by_role = by_list.setdefault(member.list_id, {})
            members = by_role.setdefault(member.role.name, [])
            members.append(member)
        # Flatten into single list sorted as per the interface.
        all_members = []
        address_of_member = attrgetter('address.email')
        for list_id in sorted(by_list):
            by_role = by_list[list_id]
            all_members.extend(
                sorted(by_role.get('owner', []), key=address_of_member))
            all_members.extend(
                sorted(by_role.get('moderator', []), key=address_of_member))
            all_members.extend(
                sorted(by_role.get('member', []), key=address_of_member))
        return all_members

    @dbconnection
    def get_member(self, store, member_id):
        """See `ISubscriptionService`."""
        members = store.query(Member).filter(Member._member_id == member_id)
        if members.count() == 0:
            return None
        else:
            assert members.count() == 1, 'Too many matching members'
            return members[0]

    @dbconnection
    def find_members(self, store, subscriber=None, list_id=None, role=None):
        """See `ISubscriptionService`."""
        # If `subscriber` is a user id, then we'll search for all addresses
        # which are controlled by the user, otherwise we'll just search for
        # the given address.
        user_manager = getUtility(IUserManager)
        if subscriber is None and list_id is None and role is None:
            return []
        # Querying for the subscriber is the most complicated part, because
        # the parameter can either be an email address or a user id.
        query = []
        if subscriber is not None:
            if isinstance(subscriber, str):
                # subscriber is an email address.
                address = user_manager.get_address(subscriber)
                user = user_manager.get_user(subscriber)
                # This probably could be made more efficient.
                if address is None or user is None:
                    return []
                query.append(or_(Member.address_id == address.id,
                                 Member.user_id == user.id))
            else:
                # subscriber is a user id.
                user = user_manager.get_user_by_id(subscriber)
                address_ids = list(address.id for address in user.addresses
                                   if address.id is not None)
                if len(address_ids) == 0 or user is None:
                    return []
                query.append(or_(Member.user_id == user.id,
                                 Member.address_id.in_(address_ids)))
        # Calculate the rest of the query expression, which will get And'd
        # with the Or clause above (if there is one).
        if list_id is not None:
            query.append(Member.list_id == list_id)
        if role is not None:
            query.append(Member.role == role)
        results = store.query(Member).filter(and_(*query))
        return sorted(results, key=_membership_sort_key)

    def __iter__(self):
        for member in self.get_members():
            yield member

    def join(self, list_id, subscriber,
             display_name=None,
             delivery_mode=DeliveryMode.regular,
             role=MemberRole.member):
        """See `ISubscriptionService`."""
        mlist = getUtility(IListManager).get_by_list_id(list_id)
        if mlist is None:
            raise NoSuchListError(list_id)
        # Is the subscriber an email address or user id?
        if isinstance(subscriber, str):
            if display_name is None:
                display_name, at, domain = subscriber.partition('@')
            return add_member(
                mlist,
                RequestRecord(subscriber, display_name, delivery_mode,
                              system_preferences.preferred_language),
                role)
        else:
            # We have to assume it's a UUID.
            assert isinstance(subscriber, UUID), 'Not a UUID'
            user = getUtility(IUserManager).get_user_by_id(subscriber)
            if user is None:
                raise MissingUserError(subscriber)
            return mlist.subscribe(user, role)

    def leave(self, list_id, email):
        """See `ISubscriptionService`."""
        mlist = getUtility(IListManager).get_by_list_id(list_id)
        if mlist is None:
            raise NoSuchListError(list_id)
        # XXX for now, no notification or user acknowledgment.
        delete_member(mlist, email, False, False)



def handle_ListDeletingEvent(event):
    """Delete a mailing list's members when the list is being deleted."""

    if not isinstance(event, ListDeletingEvent):
        return
    # Find all the members still associated with the mailing list.
    members = getUtility(ISubscriptionService).find_members(
        list_id=event.mailing_list.list_id)
    for member in members:
        member.unsubscribe()
