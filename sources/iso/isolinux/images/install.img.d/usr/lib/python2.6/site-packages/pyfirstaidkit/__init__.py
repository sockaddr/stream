# First Aid Kit - diagnostic and repair tool for Linux
# Copyright (C) 2007 Martin Sivak <msivak@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

from interpret import Tasker
from configuration import Config, Info
import logging
import sys

def initLogger(config=None):
    """We want to initialize loger when we have the filename."""
    Logger = logging.getLogger("firstaidkit")
    Logger.setLevel(logging.DEBUG)

    if config.log.method == "none":
        handler = logging.FileHandler("/dev/null")

    elif config.log.method == "stdout" or config.log.method == None:
        handler = logging.StreamHandler(sys.stdout)

    else:
        # if nothing else matches we just put it into the file.
        handler = logging.FileHandler(config.log.filename)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    Logger.addHandler(handler)

