# Copyright (C) 2010-2014 by the Free Software Foundation, Inc.
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

"""Basic WSGI Application object for REST server."""

from __future__ import absolute_import, print_function, unicode_literals

__metaclass__ = type
__all__ = [
    'make_application',
    'make_server',
    ]


import logging

from falcon import API
from falcon.api_helpers import create_http_method_map
from falcon.status_codes import HTTP_404

from wsgiref.simple_server import WSGIRequestHandler
from wsgiref.simple_server import make_server as wsgi_server

from mailman.config import config
from mailman.database.transaction import transactional
from mailman.rest.root import Root


log = logging.getLogger('mailman.http')


def path_not_found(request, response, **kws):
    # Like falcon.responders.path_not_found() but sets the body.
    response.status = HTTP_404
    response.body = b'404 Not Found'



class AdminWebServiceWSGIRequestHandler(WSGIRequestHandler):
    """Handler class which just logs output to the right place."""

    def log_message(self, format, *args):
        """See `BaseHTTPRequestHandler`."""
        log.info('%s - - %s', self.address_string(), format % args)


class RootedAPI(API):
    def __init__(self, root, *args, **kws):
        self._root = root
        super(RootedAPI, self).__init__(*args, **kws)

    @transactional
    def __call__(self, environ, start_response):
        """See `RestishApp`."""
        return super(RootedAPI, self).__call__(
            environ, start_response)

    def _get_responder(self, req):
        path = req.path
        method = req.method
        path_segments = path.split('/')
        # Since the path is always rooted at /, skip the first segment, which
        # will always be the empty string.
        path_segments.pop(0)
        if len(path_segments) == 0:
            # We're at the end of the path, so the root must be the responder.
            method_map = create_http_method_map(self._root, None, None, None)
            responder = method_map[method]
            return responder, {}, self._root
        this_segment = path_segments.pop(0)
        resource = self._root
        while True:
            # See if there's a child matching the current segment.
            # See if any of the resource's child links match the next segment.
            for name in dir(resource):
                if name.startswith('__') and name.endswith('__'):
                    continue
                attribute = getattr(resource, name)
                assert attribute is not None, name
                matcher = getattr(attribute, '__matcher__', None)
                if matcher is None:
                    continue
                if matcher == this_segment:
                    resource, path_segments = attribute(req, path_segments)
                    # The method could have truncated the remaining segments,
                    # meaning, it's consumed all the path segments, or this is
                    # the last path segment.  In that case the resource we're
                    # left at is the responder.
                    if len(path_segments) == 0:
                        # We're at the end of the path, so the root must be the
                        # responder.
                        method_map = create_http_method_map(
                            resource, None, None, None)
                        responder = method_map[method]
                        return responder, {}, resource
                    this_segment = path_segments.pop(0)
                    break
            else:
                # None of the attributes matched this path component, so the
                # response is a 404.
                return path_not_found, {}, None



def make_application():
    """Create the WSGI application.

    Use this if you want to integrate Mailman's REST server with your own WSGI
    server.
    """
    return RootedAPI(Root())


def make_server():
    """Create the Mailman REST server.

    Use this if you just want to run Mailman's wsgiref-based REST server.
    """
    host = config.webservice.hostname
    port = int(config.webservice.port)
    server = wsgi_server(
        host, port, make_application(),
        handler_class=AdminWebServiceWSGIRequestHandler)
    return server
