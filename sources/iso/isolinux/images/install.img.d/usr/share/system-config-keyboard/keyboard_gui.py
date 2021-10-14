##
## keyboard_gui.py - GUI front end code for keyboard configuration
##
## Brent Fox <bfox@redhat.com>
## Mike Fulbright <msf@redhat.com>
## Jeremy Katz <katzj@redhat.com>
## Chris Lumens <clumens@redhat.com>
## Bill Nottingham <notting@redhat.com>
## Lubomir Rintel <lkundrak@v3.sk>
##
## Copyright (C) 2002, 2003, 2007, 2008 Red Hat, Inc.
## Copyright (C) 2008, 2009 Lubomir Rintel
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


import string
import gtk
import gobject
import sys
import os
import gettext

import system_config_keyboard.keyboard as keyboard

from firstboot.config import *
from firstboot.constants import *
from firstboot.functions import *
from firstboot.module import *

sys.path.append('/usr/share/system-config-keyboard')
import keyboard_backend

_ = gettext.gettext
gettext.textdomain('system-config-keyboard')

##
## Icon for windows
##

iconFile = "/usr/share/system-config-keyboard/pixmaps/system-config-keyboard.png"
iconPixbuf = None
icon_theme = gtk.icon_theme_get_default()

try:
    iconPixbuf = icon_theme.load_icon("preferences-desktop-keyboard", 48, 0)
except:
    try:
        iconPixbuf = gtk.gdk.pixbuf_new_from_file(iconFile)
    except:
        pass

keyboardBackend = keyboard_backend.KeyboardBackend()

# hack around the fact that scroll-to in the installer acts wierd
def setupTreeViewFixupIdleHandler(view, store):
    id = {}
    id["id"] = gobject.idle_add(scrollToIdleHandler, (view, store, id))

def scrollToIdleHandler((view, store, iddict)):
    if not view or not store or not iddict:
	return

    try:
	id = iddict["id"]
    except:
	return
    
    selection = view.get_selection()
    if not selection:
	return
    
    model, iter = selection.get_selected()
    if not iter:
	return

    path = store.get_path(iter)
    col = view.get_column(0)
    view.scroll_to_cell(path, col, True, 0.5, 0.5)

    if id:
	gobject.source_remove(id)

class moduleClass(Module):
    instDataKeyboard = None

    def __init__(self):
        Module.__init__(self)
        self.icon = "system-config-keyboard.png"
        self.mode = MODE_RECONFIG
        self.priority = 20
        self.sidebarTitle = _("Keyboard")
        self.title = _("Keyboard")

        self.kbd = None

    def apply(self, interface, testing=False):
        if testing:
            return RESULT_SUCCESS

        self.getNext()
        self.kbd.write()
        # XXX should we munge the xconfig from this tool?

        # If the /etc/X11/XF86Config file exists, then change it's keyboard settings
        fullname, layout, model, variant, options = self.kbdDict[self.kbd.get()]

        keyboardBackend.modifyXconfig(fullname, layout, model, variant, options)

        try:
            #If we're in reconfig mode, this will fail because there is no self.mainWindow
            self.mainWindow.destroy()
        except:
            pass

        return RESULT_SUCCESS

    def createScreen(self, defaultByLang=None, kbd=None):
        if kbd is None:
            kbd = keyboard.Keyboard()

        self.kbd = kbd

        self.vbox = gtk.VBox(False, 10)

        iconBox = gtk.HBox(False, 5)
        iconBox.pack_start(loadToImage(iconFile))

        msgLabel = gtk.Label(_("Select the appropriate keyboard for the system."))
        msgLabel.set_line_wrap (True)
        msgLabel.set_size_request(250, -1)

        iconBox.pack_start(msgLabel)
        iconBox.set_border_width(5)

        align = gtk.Alignment()
        align.add(iconBox);
        self.vbox.pack_start(align, False)

        default = self.kbd.get()
        if not default:
            default = defaultByLang
        self.type = default

        self.modelStore = gtk.ListStore(gobject.TYPE_STRING,
                                        gobject.TYPE_STRING)
        self.modelStore.set_sort_column_id(1, gtk.SORT_ASCENDING)

        # Sort the UI by the descriptive names, not the keymap abbreviations.
        self.kbdDict = self.kbd.modelDict
        lst = self.kbdDict.items()
        lst.sort(lambda a, b: cmp(a[1][0], b[1][0]))

        for item in lst:
            iter = self.modelStore.append()
            self.modelStore.set_value(iter, 0, item[0])
            self.modelStore.set_value(iter, 1, item[1][0])

        self.modelView = gtk.TreeView(self.modelStore)
        self.col = gtk.TreeViewColumn(None, gtk.CellRendererText(), text=1)
        self.modelView.append_column(self.col)
        self.modelView.set_property("headers-visible", False)
        self.modelView.get_selection().set_mode(gtk.SELECTION_BROWSE)

        # Type ahead should search on the names, not the keymap abbreviations.
        self.modelView.set_enable_search(True)
        self.modelView.set_search_column(1)

        selection = self.modelView.get_selection()
        selection.connect("changed", self.select_row)

        iter = self.modelStore.get_iter_root()
        while iter is not None:
            if self.modelStore.get_value(iter, 0) == default:
                path = self.modelStore.get_path(iter)
                self.modelView.set_cursor(path, self.col, False)
                self.modelView.scroll_to_cell(path, self.col, True,
                                              0.5, 0.5)
                break
            iter = self.modelStore.iter_next(iter)

        self.modelViewSW = gtk.ScrolledWindow()
        self.modelViewSW.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.modelViewSW.set_shadow_type(gtk.SHADOW_IN)
        self.modelViewSW.add(self.modelView)
        self.modelViewSW.set_border_width(5)

        self.vbox.pack_start(self.modelViewSW, True)

	setupTreeViewFixupIdleHandler(self.modelView,
				      self.modelView.get_model())

    def initializeUI(self):
        pass

    def select_row(self, *args):
        rc = self.modelView.get_selection().get_selected()
        if rc:
            model, iter = rc
            if iter is not None:
                key = self.modelStore.get_value(iter, 0)
                if key:
                    self.type = key

    # This is needed by anaconda, which doesn't need to do everything
    # that the regular apply method does.
    def getNext(self):
        self.kbd.set(self.type)
        self.kbd.beenset = 1
        self.kbd.activate()

        if self.instDataKeyboard:
            self.instDataKeyboard.set(self.type)
            self.instDataKeyboard.beenset = 1
            self.instDataKeyboard.activate()

    def getScreen(self, defaultByLang, kbd):
        self.createScreen(defaultByLang, kbd)
        return self.vbox

    # All of these methods are needed for running s-c-keyboard as a
    # standalone program.
    def _okClicked(self, *args):
        return self.apply(None, False)

    def destroy(self, *args):
        gtk.main_quit()

    def stand_alone(self):
        kbd = keyboard.Keyboard()
        kbd.read()
        self.createScreen(defaultByLang="en_US", kbd=kbd)

        self.mainWindow = gtk.Dialog()
        self.mainWindow.connect("destroy", self.destroy)
        self.mainWindow.set_border_width(10)
        self.mainWindow.set_size_request(400, 350)

        self.mainWindow.set_icon(iconPixbuf)
        self.mainWindow.set_title(_(self.title))

        okButton = self.mainWindow.add_button('gtk-ok', 0)
        okButton.connect("clicked", self._okClicked)

        # Remove the hsep from the dialog.  It's ugly.
        # This is only relevant for older versions of gtk+-2.x.
        hsep = self.mainWindow.get_children()[0].get_children()[0]
        if isinstance(hsep, gtk.HSeparator):
            self.mainWindow.get_children()[0].remove(hsep)

        self.mainWindow.vbox.pack_start(self.vbox)
        self.mainWindow.show_all()

        gtk.main()

childWindow = moduleClass
