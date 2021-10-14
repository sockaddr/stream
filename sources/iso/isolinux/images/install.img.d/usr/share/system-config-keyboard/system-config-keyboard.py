#!/usr/bin/python
##
## system-config-keyboard.py: keyboard configuration startup script
##
## Copyright (C) 2002, 2003 Red Hat, Inc.
## Copyright (C) 2002, 2003 Brent Fox <bfox@redhat.com>
## Copyright (C) 2009 Lubomir Rintel <lkundrak@v3.sk>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import signal
import sys
import getopt
import gettext
 
_ = gettext.gettext
gettext.textdomain('system-config-keyboard')

if __name__ == "__main__":
    signal.signal (signal.SIGINT, signal.SIG_DFL)

def useTextMode():
    import keyboard_tui
    try:
        app = keyboard_tui.childWindow()
    except:
        import os
        os.system ("reset")
        raise

def useGuiMode():
    import keyboard_gui
    app = keyboard_gui.childWindow()
    app.stand_alone()

def useCliMode(kbdtype, help):
    import keyboard_cli
    app = keyboard_cli.childWindow(kbdtype, help)
    
kbdtype = None
help = None

opts, kbdtype = getopt.getopt(sys.argv[1:],
                              "d:h",
                              ["noui", "text", "notext", "help"])

if kbdtype:
    kbdtype = kbdtype[0]

for (opt, value) in opts:
    if opt == "--help":
        help = True
        useCliMode(kbdtype, help)

if "--noui" in sys.argv or kbdtype:
    useCliMode(kbdtype, help)

elif "--text" in sys.argv:
    useTextMode()

else:
    try:
        useGuiMode()
    except:
        if "--notext" in sys.argv:
            raise
        useTextMode()
