# Copyright (C) 1998 by the Free Software Foundation, Inc.
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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 0211-1307, USA.


"""Shared mailman errors and messages."""

__version__ = "$Revision: 539 $"


MMUnknownListError   = "MMUnknownListError"
MMBadListError       = "MMBadListError"
MMBadUserError       = "MMBadUserError"
MMBadConfigError     = "MMBadConfigError"

MMBadEmailError      = "MMBadEmailError"
MMMustDigestError    = "MMMustDigestError"
MMCantDigestError    = "MMCantDigestError"
MMNotAMemberError    = "MMNotAMemberError"
MMListNotReady       = "MMListNotReady"
MMNoSuchUserError    = "MMNoSuchUserError"
MMBadPasswordError   = "MMBadPasswordError"
MMNeedApproval       = "MMNeedApproval"
MMHostileAddress     = "MMHostileAddress"
MMAlreadyAMember     = "MMAlreadyAMember"
MMPasswordsMustMatch = "MMPasswordsMustMatch"
MMAlreadyDigested    = "MMAlreadyDigested"
MMAlreadyUndigested  = "MMAlreadyUndigested"
MMBadRequestId       = "MMBadRequestId"
MMWebSubscribeRequiresConfirmation = "MMWebSubscribeRequiresConfirmation"

MODERATED_LIST_MSG    = "Moderated list"
IMPLICIT_DEST_MSG     = "Implicit destination"
SUSPICIOUS_HEADER_MSG = "Suspicious header"
FORBIDDEN_SENDER_MSG  = "Forbidden sender"
LOOPING_POST	      = "Post already went through this list!"

MESSAGE_DECORATION_NOTE = """This text can include  <b>%(field)s</b> format
strings which are resolved against the list's attribute dictionary (__dict__).
Some useful fields are:

<dl>
  <dt>real_name
  <dd>The "pretty" name of the list, with capitalization.
  <dt>_internal_name
  <dd>The name by which the list is identified in URLs, where case
      is germane.
  <dt>host_name
  <dd>The domain-qualified host name where the list server runs.
  <dt>web_page_url
  <dd>The mailman root URL to which, eg, 'listinfo/%(_internal_name)s
      can be appended to yield the listinfo page for the list.
  <dt>description
  <dd>The brief description of the list.
  <dt>info
  <dd>The less brief list description.
</dl>
"""
