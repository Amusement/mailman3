# Copyright (C) 2010 by the Free Software Foundation, Inc.
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

"""REST for domains."""

from __future__ import absolute_import, unicode_literals

__metaclass__ = type
__all__ = [
    'ADomain',
    'AllDomains',
    ]


from restish import http, resource
from zope.component import getUtility

from mailman.interfaces.domain import (
    BadDomainSpecificationError, IDomainManager)
from mailman.rest.helpers import etag, path_to



class _DomainBase(resource.Resource):
    """Shared base class for domain representations."""

    def _domain_data(self, domain):
        """Return the domain data for a single domain."""
        return dict(
            base_url=domain.base_url,
            contact_address=domain.contact_address,
            description=domain.description,
            email_host=domain.email_host,
            self_link=path_to('domains/{0}'.format(domain.email_host)),
            url_host=domain.url_host,
            )

    def _format_domain(self, domain):
        """Format the data for a single domain."""
        return etag(self._domain_data(domain))


class ADomain(_DomainBase):
    """A domain."""

    def __init__(self, domain):
        self._domain = domain

    @resource.GET()
    def domain(self, request):
        """Return a single domain end-point."""
        domain = getUtility(IDomainManager).get(self._domain)
        if domain is None:
            return http.not_found()
        return http.ok([], self._format_domain(domain))


class AllDomains(_DomainBase):
    """The domains."""

    @resource.POST()
    def create(self, request):
        """Create a new domain."""
        # XXX 2010-02-23 barry Sanity check the POST arguments by
        # introspection of the target method, or via descriptors.
        domain_manager = getUtility(IDomainManager)
        try:
            # webob gives this to us as a string, but we need unicodes.
            kws = dict((key, unicode(value))
                       for key, value in request.POST.items())
            domain = domain_manager.add(**kws)
        except BadDomainSpecificationError:
            return http.bad_request([], 'Domain exists')
        location = path_to('domains/{0}'.format(domain.email_host))
        # Include no extra headers or body.
        return http.created(location, [], None)

    @resource.GET()
    def container(self, request):
        """Return the /domains end-point."""
        domains = list(getUtility(IDomainManager))
        if len(domains) == 0:
            resource = dict(start=None, total_size=0)
            return http.ok([], etag(resource))
        entries = [self._domain_data(domain) for domain in domains]
        # Tag the domain entries, but use the dictionaries.
        [etag(data) for data in entries]
        resource = dict(
            start=0,
            total_size=len(domains),
            entries=entries,
            )
        return http.ok([], etag(resource))
