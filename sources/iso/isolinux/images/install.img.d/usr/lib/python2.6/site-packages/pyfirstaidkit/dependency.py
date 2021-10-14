# File name: dependency.py
# Date:      2008/04/18
# Author:    Martin Sivak
#
# Copyright (C) Red Hat 2008
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# in a file called COPYING along with this program; if not, write to
# the Free Software Foundation, Inc., 675 Mass Ave, Cambridge, MA
# 02139, USA.

import logging
import copy
from errors import *

Logger=logging.getLogger("firstaidkit")

class Dependencies(object):
    """Encapsulate flags used to control the dependencies between plugins"""
    def __init__(self):
        self._provide = None
        self._known = set()
        self.reset()

    def provide(self, id, setactionflag = True):
        """Add flag"""
        Logger.info("Setting dependency flag %s", id)
        self._provide.add(id)
        #Action flags denote activity happening on some regular flag
        if setactionflag: self._provide.add(id+"?")

    def unprovide(self, id, setactionflag = True):
        """Remove flag"""
        Logger.info("Resetting dependency flag %s", id)
        try:
            self._provide.remove(id)
        except KeyError: #not there
            pass
        if setactionflag: self._provide.add(id+"?")

    donotprovide = unprovide #alias
    failed = unprovide #alias

    def require(self, id):
        """Return True if flag is present, otherwise false"""
        return id in self._provide

    def introduce(self, s):
        """Notifies the system about dep names used in the plugins.

        This allows us to list them in help"""
        self._known = self._known.union(s)

    def known(self):
        """Returns list of known flags"""
        return list(self._known.union(self._provide))

    def valid(self):
        """Returns list of valid/provided flags"""
        return list(self._provide)

    def reset(self):
        self._provide = set()

