# -*- coding: utf-8 -*-
#
# timezone_map_gui.py: gui timezone map widget.
#
# Copyright © 2001 - 2007, 2009 Red Hat, Inc.
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
# Matt Wilson <msw@redhat.com>
# Brent Fox <bfox@redhat.com>
# Nils Philippsen <nphilipp@redhat.com>
# Chris Lumens <clumens@redhat.com>
# Thomas Wörner <twoerner@redhat.com>

import gobject
import pango
import gtk
try:
    import gnomecanvas
except ImportError:
    import gnome.canvas as gnomecanvas
import re
import math
import random
import sys

from scdate.core.util import _

class Enum(object):
    def __init__ (self, *args):
        i = 0
        for arg in args:
            self.__dict__[arg] = i
            i += 1

class TimezoneMap (gtk.VBox):
    # these values are percentages
    zoom_initial = 100.0
    zoom_lower = 100.0
    # the map zooms in to this value when a city is selected
    zoom_auto = 300.0
    zoom_upper = 500.0
    zoom_step = 25.0
    zoom_page = 100.0
    #force order of destruction for a few items.
    def __del__ (self):
        del self.arrow
        del self.shaded_map
        del self.markers
        del self.currentMapX
        del self.currentMapText
        del self.highlightedMapText
        del self.highlightedMapBox

    def map_canvas_init (self, map, viewportWidth):
        self.canvas = gnomecanvas.Canvas ()
        root = self.canvas.root ()
        pixbuf = gtk.gdk.pixbuf_new_from_file (map)

        self.mapWidth = pixbuf.get_width ()
        self.mapHeight = pixbuf.get_height ()
        self.mapShown = (0.0, 0.0, self.mapWidth, self.mapHeight)
        self.viewportWidth = viewportWidth
        self.viewportHeight = int (float (self.viewportWidth) / float (self.mapWidth) * float (self.mapHeight))
        self.long = -180.0
        self.lat = -90.0

        root.add (gnomecanvas.CanvasPixbuf, x=0, y=0, pixbuf=pixbuf, anchor=gtk.ANCHOR_NW)
        x1, y1, x2, y2 = root.get_bounds ()
        self.canvas.set_scroll_region (x1, y1, x2, y2)
        self.canvas.set_center_scroll_region (True)
        self.canvas.set_size_request (self.viewportWidth, self.viewportHeight)

        table = gtk.Table (rows = 2, columns = 3, homogeneous = False)
        table.attach (self.canvas, 1, 2, 0, 1, xoptions = (), yoptions = ())

        # Set up horizontal scrollbar
        self.hadj = self.canvas.get_hadjustment ()
        self.hscr = gtk.HScrollbar (self.hadj)
        table.attach (self.hscr, 1, 2, 1, 2, xoptions = gtk.FILL, yoptions = ())

        # Set up vertical scrollbar
        self.vadj = self.canvas.get_vadjustment ()
        self.vscr = gtk.VScrollbar (self.vadj)
        table.attach (self.vscr, 2, 3, 0, 1, xoptions = (), yoptions = gtk.FILL)

        self.pack_start (table, False, False)

        root.connect ("event", self.mapEvent)
        self.canvas.connect ("event", self.canvasEvent)

        # set up the zoom slider
        vbox = gtk.VBox ()
        vbox.set_spacing (5)
        table.attach (vbox, 0, 1, 0, 1, xoptions = (), yoptions = gtk.FILL)

        def zoom_button_press_cb (button, direction):
            si = self.zoomAdjustment.get_property ('page_increment')
            val = self.zoomAdjustment.get_value ()
            self.zoomAdjustment.set_value (val + si * direction)
            self.zoomAdjustment.changed ()

        #vbox.pack_start (gtk.Label (_('Magnification: small')), False, False)
        #vbox.pack_start (gtk.Label ('+'), False, False)
        zoomInImage = gtk.Image ()
        zoomInImage.set_from_stock (gtk.STOCK_ZOOM_IN, gtk.ICON_SIZE_BUTTON)
        zoomInButton = gtk.Button ()
        zoomInButton.set_image (zoomInImage)
        zoomInButton.connect ('clicked', zoom_button_press_cb, 1)
        vbox.pack_start (zoomInButton, False, False)

        def zoom_adj_value_changed_cb (adj, *rest):
            # round value
            adj.set_value (float (int (adj.get_value () / self.zoom_step + 0.5) * self.zoom_step))
            # update labels
            self.city_labels_update ()

        self.zoomAdjustment = gtk.Adjustment (self.zoom_initial, self.zoom_lower, self.zoom_upper, self.zoom_step, self.zoom_page)
        self.zoomAdjustment.connect ('value-changed', zoom_adj_value_changed_cb)

        def zoom_value_changed_cb (adj, *rest):
            self.zoom_set (self.zoomAdjustment.get_value ())

        self.zoomScale = gtk.VScale (self.zoomAdjustment)
        self.zoomScale.set_inverted (True)
        self.zoomScale.connect ('value-changed', zoom_value_changed_cb)
        self.zoomScale.set_digits (0)
        self.zoomScale.set_draw_value (False)
        self.zoomFactor = self.zoom_initial / 100.0
        self.zoom_set (self.zoom_initial)
        vbox.pack_start (self.zoomScale, True, True)

        #vbox.pack_start (gtk.Label (_('large')), False, False)
        #vbox.pack_start (gtk.Label ('-'), False, False)
        zoomOutImage = gtk.Image ()
        zoomOutImage.set_from_stock (gtk.STOCK_ZOOM_OUT, gtk.ICON_SIZE_BUTTON)
        zoomOutButton = gtk.Button ()
        zoomOutButton.set_image (zoomOutImage)
        zoomOutButton.connect ('clicked', zoom_button_press_cb, -1)
        vbox.pack_start (zoomOutButton, False, False)

        self.motion_data = None
        self.motion_origin = (0, 0)

        self.allow_zoom = True

    def timezone_list_init (self, default):
        root = self.canvas.root ()
        self.treeStore = gtk.TreeStore (gobject.TYPE_STRING,
                                        gobject.TYPE_STRING,
                                        gobject.TYPE_PYOBJECT,
                                        gobject.TYPE_STRING)
        self.treeStoreRoots = {}
        nonGeoTzItem = 10

        for entry in self.zonetab.getEntries ():
            if entry.tz[0:4] != 'Etc/':
                try:
                    tz_root_str, tz_node_str = \
                            entry.translated_tz.rsplit ('/', 1)
                except ValueError:
                    print >>sys.stderr, "Couldn't split timezone name fields:\nUntranslated TZ: %s\nTranslated TZ: %s" % (entry.tz, entry.translated_tz)
                    raise
                tzsortprefix = "0/"
            else:
                tz_root_str = _('Non-geographic timezones')
                tz_node_str = entry.translated_tz.split("/", 1)[1]
                tzsortprefix = "%u/" % nonGeoTzItem
                nonGeoTzItem += 1
            tz_root_str_split = tz_root_str.split ('/')
            for depth in xrange (len (tz_root_str_split)):
                root_joined_str = '/'.join (tz_root_str_split[:depth])
                root_joined_str_1 = '/'.join (tz_root_str_split[:depth+1])
                if depth == 0:
                    riter = None
                else:
                    riter = self.treeStoreRoots[root_joined_str]
                if not self.treeStoreRoots.has_key (root_joined_str_1):
                    iter = self.treeStore.append (riter)
                    self.treeStore.set_value (iter, self.columns.TZ, tz_root_str_split [depth])
                    self.treeStore.set_value (iter, self.columns.COMMENTS, None)
                    self.treeStore.set_value (iter, self.columns.ENTRY, None)
                    self.treeStore.set_value (iter, self.columns.TZSORT, tzsortprefix + tz_root_str_split [depth])
                    self.treeStoreRoots[root_joined_str_1] = iter

            iter = self.treeStore.append (self.treeStoreRoots[tz_root_str])
            self.treeStore.set_value (iter, self.columns.TZ, tz_node_str)
            if entry.comments:
                self.treeStore.set_value (iter, self.columns.COMMENTS,
                                         _(entry.comments))
            else:
                self.treeStore.set_value (iter, self.columns.COMMENTS, "")
            self.treeStore.set_value (iter, self.columns.ENTRY, entry)
            self.treeStore.set_value (iter, self.columns.TZSORT, (tzsortprefix + tz_node_str).replace ('+', '+1').replace ('-', '-0'))

            if entry.long != None and entry.lat != None:
                x, y = self.map2canvas (entry.lat, entry.long)
                marker = root.add (gnomecanvas.CanvasText, x=x, y=y,
                                text=u'\u00B7', fill_color='yellow',
                                anchor=gtk.ANCHOR_CENTER,
                                weight=pango.WEIGHT_BOLD)
                self.markers[entry.tz] = marker

            if entry.tz == default:
                self.currentEntry = entry
            if entry.tz == "America/New York":
                #In case the /etc/sysconfig/clock is messed up, use New York as default
                self.fallbackEntry = entry

        self.treeStore.set_sort_column_id (self.columns.TZSORT, gtk.SORT_ASCENDING)

        self.treeView = gtk.TreeView (self.treeStore)
        selection = self.treeView.get_selection ()
        selection.connect ("changed", self.selectionChanged)
        #self.treeView.connect ('button_press_event', self.selectionChanged_wrap)
        self.treeView.set_property ("headers-visible", False)
        col = gtk.TreeViewColumn (None, gtk.CellRendererText (), text=0)
        self.treeView.append_column (col)
        col = gtk.TreeViewColumn (None, gtk.CellRendererText (), text=1)
        self.treeView.append_column (col)

        sw = gtk.ScrolledWindow ()
        sw.add (self.treeView)
        sw.set_shadow_type (gtk.SHADOW_IN)
        self.pack_start (sw, True, True)

    def arrow_init (self):
        root = self.canvas.root ()
        self.arrow = root.add (gnomecanvas.CanvasLine,
                               fill_color = 'limegreen',
                               width_pixels = 2,
                               first_arrowhead = False,
                               last_arrowhead = True,
                               arrow_shape_a = 4.0,
                               arrow_shape_b = 8.0,
                               arrow_shape_c = 4.0,
                               points = (0.0, 0.0, 0.0, 0.0))
        self.arrow.hide ()

    def cityname_format (self, name):
        componentsReversed = reversed (name.split ('/'))
        return _(', ').join (componentsReversed)

    def currentCityLabel_init (self):
        self.currentCityLabel = gtk.Label ('')
        self.currentCityLabel.set_ellipsize (pango.ELLIPSIZE_END)
        self.pack_start (self.currentCityLabel, False, True)
        self.currentCityLabel.set_alignment (0.0, 0.0)
        self.currentCityLabel.show ()

    def currentCityLabel_set (self):
        if self.currentEntry.comments and len (self.currentEntry.comments):
            labelText = _('Selected city: %(city)s (%(comments)s)') % {'city': self.cityname_format (self.currentEntry.translated_tz), 'comments': _(self.currentEntry.comments)}
        else:
            labelText = _('Selected city: %s') % self.cityname_format (self.currentEntry.translated_tz)

        self.currentCityLabel.set_text (labelText)

    def city_label_init (self, what):
        if what not in ('current', 'highlighted'):
            raise AttributeError (what)
        root = self.canvas.root ()
        if what == 'highlighted':
            # box
            self.highlightedMapBox = root.add (gnomecanvas.CanvasRect,
                x1 = 0, y1 = 0, x2 = 0, y2 = 0, fill_color_rgba = 0xffffffff)

            self.highlightedMapBox.raise_ (1)
            self.highlightedMapBox.hide ()

        # text
        setattr (self, what + "MapText", root.add (gnomecanvas.CanvasText,
            text = '', x = 0, y = 0, anchor = gtk.ANCHOR_N,
            fill_color = 'black', weight = pango.WEIGHT_NORMAL))
        text = getattr (self, what + "MapText")
        if what == 'highlighted':
            text.raise_ (1)
        text.hide ()

    def __init__(self, zonetab, default="America/New_York",
            map='../pixmaps/map1440.png', viewportWidth = 480, tzActionLabel = gtk.Label (_("Please select the nearest city in your time zone:"))):
        gtk.VBox.__init__(self, False, 5)

        # set up members
        self.columns = Enum ("TZ", "COMMENTS", "ENTRY", "TZSORT")
        self.currentEntry = None
        self.fallbackEntry = None
        self.highlightedEntry = None
        self.zonetab = zonetab
        self.markers = {}
        self.tzActionLabel = tzActionLabel

        # set up the map canvas
        self.map_canvas_init (map, viewportWidth)

        # marker for currently selected city
        root = self.canvas.root ()
        self.currentMapX = root.add (gnomecanvas.CanvasText, text='x',
                                fill_color='red', anchor=gtk.ANCHOR_CENTER,
                                weight=pango.WEIGHT_BOLD)

        # label for currently selected city
        self.currentCityLabel_init ()

        # set up the arrows
        self.arrow_init ()

        # set up the label for the currently selected city
        self.city_label_init ("current")

        # set up list of time zones
        self.timezone_list_init (default)

        # set up the label for the highlighted city
        self.city_label_init ("highlighted")

        self.setCurrent (zonetab.findEntryByTZ (default))
        (self.lastx, self.lasty) = (0, 0)

        self.canvas.set_tooltip_text (_("Use button 2 or 3 for panning and the scrollwheel to zoom in or out."))

    def zoom_set (self, factor_percent):
        factor = factor_percent / 100.0
        oldLong = self.long
        oldLat = self.lat
        oldLongWidth = 360.0 / self.zoomFactor
        oldLatHeight = 180.0 / self.zoomFactor
        oldZoomFactor = self.zoomFactor
        self.zoomFactor = factor
        newLongWidth = 360.0 / self.zoomFactor
        newLatHeight = 180.0 / self.zoomFactor
        newLong = (oldLong + oldLongWidth - newLongWidth) / 2.0
        newLat = (oldLat + oldLatHeight - newLatHeight) / 2.0
        self.canvas.set_pixels_per_unit (self.zoomFactor * float (self.viewportWidth) / float (self.mapWidth))
        self.vp_set (newLong, newLat)
        try:
            if self.currentCityLabel:
                self.currentCityLabel_set ()
        except AttributeError:
            pass

        self.hadj.set_property ('step_increment', float (self.viewportWidth) / self.zoomFactor / 2)
        self.hadj.set_property ('page_increment', float (self.viewportWidth) / self.zoomFactor)
        self.vadj.set_property ('step_increment', float (self.viewportHeight) / self.zoomFactor / 2)
        self.vadj.set_property ('page_increment', float (self.viewportHeight) / self.zoomFactor)

    def vp_set (self, long, lat):
        # clamp longitude
        long += 180.0
        long %= 360.0
        long -= 180.0

        self.long = long

        # clamp latitude
        if lat + 180.0 / self.zoomFactor > 90.0:
            lat = 90.0 - 180.0 / self.zoomFactor

        self.lat = lat

    def get_shown_region (self):
        _x, _y = self.canvas.get_scroll_offsets ()
        x, y = self.canvas.c2w (_x, _y)
        width = self.mapWidth / self.zoomFactor
        height = self.mapHeight / self.zoomFactor
        return x, y, x + width, y + height

    def get_shown_region_long_lat (self):
        xmin, ymin, xmax, ymax = self.get_shown_region ()
        longmin, latmax = self.canvas2map (xmin, ymin)
        longmax, latmin = self.canvas2map (xmax, ymax)
        return longmin, latmin, longmax, latmax

    def get_caption_anchor_offsets (self, x, y, map_global):
        if map_global:
            x1, y1, x2, y2 = 0, 0, self.mapWidth - 1, self.mapHeight - 1
        else:
            x1, y1, x2, y2 = self.get_shown_region ()
        w, h = x2 - x1, y2 - y1

        if map_global:
            xw = xe = int (x1 + 0.9 * w)
            yns = int (y1 + 0.9 * h)
        else:
            xw = int (x1 + w/3)
            xe = int (x2 - w/3)
            yns = int (y1 + h/2)

        if y < yns:
            northsouth = 'N'
            yoffset = 20
        else:
            northsouth = 'S'
            yoffset = -20
        if x < xw:
            eastwest = 'W'
            xoffset = 20
        elif x > xe:
            eastwest = 'E'
            xoffset = -20
        else:
            eastwest = ''
            xoffset = 0
        anchor = getattr (gtk, 'ANCHOR_%s%s' % (northsouth, eastwest))
        return anchor, xoffset, yoffset

    def getCurrent (self):
        return self.currentEntry

    def selectionChanged_wrap (self, widget, *args):
        self.selectionChanged (widget.get_selection (), *args)

    def selectionChanged (self, selection, *args):
        (model, iter) = selection.get_selected ()
        if iter is None:
            return
        entry = self.treeStore.get_value (iter, self.columns.ENTRY)
        if entry:
            self.setCurrent (entry, skipList=1)
            if entry.long != None and entry.lat != None:
                self.move_to (entry.long, entry.lat)

    def move_to (self, long, lat):
        self.vp_set (long, lat)
        x, y = self.map2canvas (lat, long)
        zoom = self.zoomFactor * float (self.viewportWidth) / float (self.mapWidth)
        self.canvas.scroll_to (int (x * zoom - self.viewportWidth / 2), int (y * zoom - self.viewportHeight / 2))
        self.canvas.update_now ()

    def _city_label_update (self, what):
        if what not in ("current", "highlighted"):
            raise AttributeError

        entry = getattr (self, what + "Entry")
        text = getattr (self, what + "MapText")

        if what == "current":
            labelText = entry.translated_tz.split ("/")[-1]
            box = None
            map_global = True
            color = "red"
        else:
            labelText = self.cityname_format (entry.translated_tz)
            box = self.highlightedMapBox
            map_global = False
            color = "black"

        if entry.long != None and entry.lat != None:
            x, y = self.map2canvas (entry.lat, entry.long)
            anchor, xoffset, yoffset = self.get_caption_anchor_offsets (x, y, map_global)
            text.set (text = labelText, x = x + xoffset / (self.zoomFactor),
                    y = y + yoffset / (self.zoomFactor), anchor = anchor,
                    fill_color = color)

            x1, y1, x2, y2 = text.get_bounds ()
            text.show ()
            if box:
                box.set (x1 = x1, y1 = y1, x2 = x2, y2 = y2)
                box.show ()
        else:
            text.hide ()
            if box:
                box.hide ()

    def city_labels_update (self):
        self._city_label_update ("current")
        if self.highlightedEntry:
            self._city_label_update ("highlighted")
        else:
            self.highlightedMapText.hide ()
            self.highlightedMapBox.hide ()

    def mapMoveEvent (self, event):
        if not self.motion_data:
            # draw arrow
            x1, y1 = self.canvas.root ().w2i (event.x, event.y)
            long, lat = self.canvas2map (x1, y1)
            #print event.x, event.y, "->", x1, y1
            #print r['x'], r['y'], r['w'], r['h'], r['x'] + r['w'] - 1, r['y'] + r['h'] - 1
            longmin, latmin, longmax, latmax = self.get_shown_region_long_lat ()
            #print long, lat
            #print longmin, latmin, longmax, latmax
            last = self.highlightedEntry
            self.highlightedEntry = self.zonetab.findNearest (long, lat, longmin, latmin, longmax, latmax, self.currentEntry)
            self.city_labels_update ()
            if self.highlightedEntry:
                x2, y2 = self.map2canvas (self.highlightedEntry.lat,
                                        self.highlightedEntry.long)
                self.arrow.set (points = (x1, y1, x2, y2))
                self.arrow.show ()
            else:
                self.arrow.hide ()
        else:
            # canvas motion
            x0, y0 = self.motion_origin
            ex1, ey1 = self.motion_data
            ex2, ey2 = self.canvas.get_pointer()

            dx = ex2 - ex1
            dy = ey2 - ey1

            self.hscr.set_value(x0 - dx)
            self.vscr.set_value(y0 - dy)

    def mapMouseButtonEvent (self, event):
        if event.button == 1:
            if event.type == gtk.gdk.BUTTON_PRESS:
                if self.highlightedEntry:
                    if self.zoomFactor * 100.0 < self.zoom_auto:
                        self.zoomAdjustment.set_value (self.zoom_auto)
                        self.zoomAdjustment.changed ()
                        self.city_labels_update ()
                    self.setCurrent (self.highlightedEntry)
        elif event.button in (2, 3) and self.zoomFactor > 1.0:
            if event.type == gtk.gdk.BUTTON_PRESS:
                # motion start
                self.allow_zoom = False
                self.motion_data =  self.canvas.get_pointer()
                self.motion_origin = (self.hscr.get_value(),
                                      self.vscr.get_value())
                self.arrow.hide ()
                self.highlightedMapText.hide ()
                self.highlightedMapBox.hide ()
                win = self.get_toplevel ().window
                cur = gtk.gdk.Cursor (gtk.gdk.FLEUR)
                win.set_cursor (cur)
            elif event.type == gtk.gdk.BUTTON_RELEASE:
                # motion end
                self.allow_zoom = True
                self.motion_data = None
                self.mapMoveEvent (event)
                win = self.get_toplevel ().window
                win.set_cursor (None)

    def mapEvent (self, widget, event=None):
        if event.type == gtk.gdk.MOTION_NOTIFY or event == gtk.gdk.ENTER_NOTIFY:
            self.mapMoveEvent (event)
        elif event.type in (gtk.gdk.BUTTON_PRESS, gtk.gdk.BUTTON_RELEASE):
            self.mapMouseButtonEvent (event)

    def canvasEvent (self, widget, event):
        if event.type == gtk.gdk.LEAVE_NOTIFY or self.motion_data:
            self.arrow.hide ()
            self.highlightedMapText.hide ()
            self.highlightedMapBox.hide ()
        elif (event.type == gtk.gdk.MOTION_NOTIFY or event == gtk.gdk.ENTER_NOTIFY) and not self.motion_data:
            self.arrow.show ()
            self.highlightedMapText.show ()
            self.highlightedMapBox.show ()
        elif self.allow_zoom and (event.type == gtk.gdk.SCROLL) and (event.direction in (gtk.gdk.SCROLL_UP, gtk.gdk.SCROLL_DOWN)):
            direction = (event.direction == gtk.gdk.SCROLL_UP) and 1 or -1
            si = self.zoomAdjustment.get_property ('step_increment')
            val = self.zoomAdjustment.get_value ()
            self.zoomAdjustment.set_value (val + si * direction)
            self.zoomAdjustment.changed ()
            self.city_labels_update ()

    def find_tz_iter_for_iter (self, iter):
        entry_iter = None
        child = self.treeStore.iter_children (iter)
        while child:
            entry_iter = self.find_tz_iter_for_iter (child)
            if entry_iter:
                break
            child = self.treeStore.iter_next (child)
        if not entry_iter:
            entry = self.treeStore.get_value (iter, self.columns.ENTRY)
            if entry == self.currentEntry:
                entry_iter = iter
        return entry_iter

    def find_tz_iter (self):
        iter = self.treeStore.get_iter_first ()
        while iter:
            found_iter = self.find_tz_iter_for_iter (iter)
            if found_iter:
                return found_iter
            iter = self.treeStore.iter_next (iter)
        return None

    def updateTimezoneList (self):
        iter = self.find_tz_iter ()
        if iter:
            selection = self.treeView.get_selection ()
            selection.unselect_all ()
            path = self.treeStore.get_path (iter)
            col = self.treeView.get_column (0)
            self.treeView.expand_to_path (path)
            self.treeView.scroll_to_cell (path, col)
            self.treeView.set_cursor (path)

    def setCurrent (self, entry, skipList=0):
        # Draw marker for old currentEntry.
        if self.currentEntry and self.markers.has_key (self.currentEntry.tz):
            self.markers[self.currentEntry.tz].show ()

        if not entry:
            # If the value in /etc/sysconfig/clock is invalid, default to New York
            self.currentEntry = self.fallbackEntry
        else:
            self.currentEntry = entry

        # Hide new currentEntry, draw big red X over it instead.
        if self.currentEntry.long and self.currentEntry.lat:
            self.markers[self.currentEntry.tz].hide ()
            x, y = self.map2canvas (self.currentEntry.lat, self.currentEntry.long)
            self.currentMapX.set (x=x, y=y)
            self.currentMapX.show ()
            self.currentCityLabel_set ()
            self.city_labels_update ()
            self.currentMapText.show ()
        else:
            self.currentMapX.hide ()
            self.currentMapText.hide ()

        if skipList:
            return

        self.updateTimezoneList ()

    def map2canvas (self, lat, long):
        x2 = self.mapWidth
        y2 = self.mapHeight
        x = x2 / 2.0 + (x2 / 2.0) * long / 180.0
        y = y2 / 2.0 - (y2 / 2.0) * lat / 90.0
        return (x, y)

    def canvas2map (self, x, y):
        x2 = self.mapWidth
        y2 = self.mapHeight
        long = (x - x2 / 2.0) / (x2 / 2.0) * 180.0
        lat = (y2 / 2.0 - y) / (y2 / 2.0) * 90.0
        #print x, y, "->", long, lat
        return (long, lat)

if __name__ == "__main__":
    from scdate.core import zonetab
    zonetab = zonetab.ZoneTab ()
    win = gtk.Window ()
    if gtk.__dict__.has_key ("main_quit"):
        win.connect ('destroy', gtk.main_quit)
    else:
        win.connect ('destroy', gtk.mainquit)
    map = TimezoneMap (zonetab)
    vbox = gtk.VBox ()
    vbox.pack_start (map)
    button = gtk.Button ("Quit")
    if gtk.__dict__.has_key ("main_quit"):
        button.connect ("pressed", gtk.main_quit)
    else:
        button.connect ("pressed", gtk.mainquit)
    vbox.pack_start (button, False, False)
    win.add (vbox)
    win.show_all ()
    if gtk.__dict__.has_key ("main"):
        gtk.main ()
    else:
        gtk.mainloop ()

