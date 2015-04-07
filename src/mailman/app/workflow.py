# Copyright (C) 2015 by the Free Software Foundation, Inc.
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

"""Generic workflow."""

__all__ = [
    'Workflow',
    ]


import json
import logging

from collections import deque
from mailman.interfaces.workflow import IWorkflowStateManager
from zope.component import getUtility


COMMASPACE = ', '
log = logging.getLogger('mailman.error')



class Workflow:
    """Generic workflow."""

    SAVE_ATTRIBUTES = ()
    INITIAL_STATE = None

    def __init__(self):
        self.token = None
        self._next = deque()
        self.push(self.INITIAL_STATE)

    def __iter__(self):
        return self

    def push(self, step):
        self._next.append(step)

    def _pop(self):
        name = self._next.popleft()
        step = getattr(self, '_step_{}'.format(name))
        return name, step

    def __next__(self):
        try:
            name, step = self._pop()
            return step()
        except IndexError:
            raise StopIteration
        except:
            log.exception('deque: {}'.format(COMMASPACE.join(self._next)))
            raise

    def save(self):
        assert self.token, 'Workflow token must be set'
        state_manager = getUtility(IWorkflowStateManager)
        data = {attr: getattr(self, attr) for attr in self.SAVE_ATTRIBUTES}
        # Note: only the next step is saved, not the whole stack.  This is not
        # an issue in practice, since there's never more than a single step in
        # the queue anyway.  If we want to support more than a single step in
        # the queue *and* want to support state saving/restoring, change this
        # method and the restore() method.
        if len(self._next) == 0:
            step = None
        elif len(self._next) == 1:
            step = self._next[0]
        else:
            raise AssertionError(
                "Can't save a workflow state with more than one step "
                "in the queue")
        state_manager.save(
            self.__class__.__name__,
            self.token,
            step,
            json.dumps(data))

    def restore(self):
        state_manager = getUtility(IWorkflowStateManager)
        state = state_manager.restore(self.__class__.__name__, self.token)
        if state is not None:
            self._next.clear()
            if state.step:
                self._next.append(state.step)
            if state.data is not None:
                for attr, value in json.loads(state.data).items():
                    setattr(self, attr, value)
