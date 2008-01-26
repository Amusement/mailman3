# Copyright (C) 2007 by the Free Software Foundation, Inc.
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

"""Interface describing the basics of chains and links."""

from munepy import Enum
from zope.interface import Interface, Attribute



class LinkAction(Enum):
    # Jump to another chain.
    jump = 0
    # Take a detour to another chain, returning to the original chain when
    # completed (if no other jump occurs).
    detour = 1
    # Stop processing all chains.
    stop = 2
    # Continue processing the next link in the chain.
    defer = 3
    # Run a function and continue processing.
    run = 4



class IChainLink(Interface):
    """A link in the chain."""

    rule = Attribute('The rule to run for this link.')

    action = Attribute('The LinkAction to take if this rule matches.')

    chain = Attribute('The chain to jump or detour to.')

    function = Attribute(
        """The function to execute.

        The function takes three arguments and returns nothing.
        :param mlist: the IMailingList object
        :param msg: the message being processed
        :param msgdata: the message metadata dictionary
        """)



class IChain(Interface):
    """A chain of rules."""

    name = Attribute('Chain name; must be unique.')
    description = Attribute('A brief description of the chain.')

    def __iter__():
        """Iterate over all the IChainLinks in this chain.

        :return: an IChainLink.
        """

    def get_rule(name):
        """Lookup and return the named rule.

        :param name: The name of the rule to return.  This may be a globally
            registered rule name, in which case it must be unique, or it may
            be a rule defined locally to the chain.
        :return: The named `IRule`.
        :raises: KeyError if the named rule cannot be found.
        """



class IMutableChain(IChain):
    """Like `IChain` but can be mutated."""

    def append_link(link):
        """Add a new chain link to the end of this chain.

        :param link: The chain link to add.
        """

    def flush():
        """Delete all links in this chain."""
