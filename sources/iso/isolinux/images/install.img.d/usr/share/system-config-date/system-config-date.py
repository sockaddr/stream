#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# system-config-date - Program creates a user interface
#                      that allows the system time, system date,
#                      time zone, and ntpd configuration to be easily set
#
# Copyright © 2001 - 2003, 2005, 2009 Red Hat, Inc.
# Copyright © 2001 - 2003 Brent Fox <bfox@redhat.com>
#                         Tammy Fox <tfox@redhat.com>
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Authors:
# Brent Fox <bfox@redhat.com>
# Tammy Fox <tfox@redhat.com>
# Nils Philippsen <nphilipp@redhat.com>

import sys
import signal
import getopt

from scdate.core.util import _

def showhelp ():
    sys.stderr.write (_("""Usage: system-config-date [options]
Enduser options:
-h|--help        Display this help message
Reserved options:
--page <page>    Display page <page>
"""))

def useGuiMode(page):
    try:
        __import__("gtk")
    except RuntimeError, e:
        raise SystemExit(_("Error while initializing GUI toolkit: %(error)s\n"
            "This program must be run in a graphical environment.") %
            dict(error=str(e)))
        sys.exit(1)

    import scdMainWindow

    scdMainWindow.scdMainWindow(page).stand_alone()

if __name__ == "__main__":
    signal.signal (signal.SIGINT, signal.SIG_DFL)

    try:
        opts, rest = getopt.gnu_getopt(sys.argv[1:], "h", ["help"])
    except getopt.GetoptError, g:
        sys.stderr.write (_("option(s) '%s' not recognized\n") % g.opt)
        showhelp ()
        sys.exit (1)

    if rest:
        sys.stderr.write (_("option(s) '%s' not recognized\n") % ' '.join (rest))
        showhelp ()
        sys.exit (1)

    page = 0
    for opt, value in opts:
        if opt == '-h' or opt == '--help':
            showhelp ()
            sys.exit (0)
        if opt == "--page":
            page = int(value)

    useGuiMode(page)
