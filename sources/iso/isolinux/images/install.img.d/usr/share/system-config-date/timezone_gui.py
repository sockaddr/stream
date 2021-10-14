# -*- coding: utf-8 -*-
#
# timezone_gui.py - Program creates a user interface
#                   that allows the system time, system date,
#                   time zone, and ntpd configuration to be easily set
#
# Copyright © 2001 - 2007, 2009 Red Hat, Inc.
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

import gtk
import gobject
import time
import sys
import scdMainWindow
from timezone_map_gui import TimezoneMap
from scdate.core import zonetab

def timezone_widget_create (xml):
    folder = "/usr/share/system-config-date/"
    mappath = folder + "pixmaps/map1440.png"
    tzActionLabel = xml.get_widget ('tzActionLabel')
    default = scdMainWindow.timezoneBackend.getTimezoneInfo()[0]
    widget = TimezoneMap(zonetab.ZoneTab (), default, map=mappath, tzActionLabel = tzActionLabel)
    widget.show_all ()
    return widget

custom_widgets = {'timezone_widget_create': timezone_widget_create}

class timezonePage (gtk.VBox):
    def __init__(self, xml):
        self.xml = xml
        self.mainVBox = self.xml.get_widget ("tz_vbox")
        self.timezone = scdMainWindow.timezoneBackend.getTimezoneInfo ()
        self.default, self.asUTC = self.timezone

        self.tz = self.xml.get_widget ("tz")

        self.utcCheck = self.xml.get_widget ("utc_check")

        if scdMainWindow.timezoneBackend.canHwClock:
            if self.asUTC == "true":
                self.utcCheck.set_active (True)
            else:
                self.utcCheck.set_active (False)
        else:
            self.utcCheck.set_active (True)
            self.utcCheck.set_sensitive (True)

    def getVBox(self):
        return self.mainVBox

    def getSmallVBox(self):
        self.mainVBox.remove(self.mainVBox.get_children()[0])
        return self.mainVBox

    def getTimezoneInfo(self):
        return self.tz.getCurrent().tz, self.utcCheck.get_active()
