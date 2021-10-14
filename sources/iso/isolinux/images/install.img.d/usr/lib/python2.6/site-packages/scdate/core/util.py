# -*- coding: utf-8 -*-
#
# util.py: utility functions
#
# Copyright © 2010 Red Hat, Inc.
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
# Nils Philippsen <nphilipp@redhat.com>

import gettext
import locale
import os

__all__ = ('ugettext', '_', 'N_')

class DynLangTranslator(object):
    """This class allows dynamically changing languages during runtime of a
    program (anaconda), catalogs will be reloaded with the new settings if this
    happens.

    It also allows registering callbacks that are invoked if a language change
    is detected."""

    def __init__(self, domain):
        self.domain = domain
        self.langenv = None
        self.lang_change_callbacks = []

        self._check_set_lang()

    def _lang_changed(self):
        for cb_entry in self.lang_change_callbacks:
            if cb_entry is None:
                continue

            (callback, p, k) = cb_entry
            callback(*p, **k)

    def _get_langenv(self):
        e = os.environ
        return (e.get('LANG'), e.get('LC_MESSAGES'), e.get('LC_ALL'),
                locale.getlocale())

    def _check_set_lang(self):
        # check if the language has changed since last use
        langenv = self._get_langenv()
        if self.langenv == langenv:
            return
        self.langenv = langenv

        try:
            self.tx = gettext.translation(self.domain)
        except IOError:
            self.tx = gettext.NullTranslations()

        self._lang_changed()

    def register_lang_change_callback(self, callback, *p, **k):
        """Register a callback that is invoked if the language is changed.

        Returns the id of the registered callback."""

        self.lang_change_callbacks.append((callback, p, k))
        return len(self.lang_change_callbacks)
        self.subscribers.add(callback)

    def unsubscribe_lang_change(self, id):
        """Unregister a callback that was previously registered by its id."""

        self.lang_change_callbacks[id] = None

    @property
    def ugettext(self):
        self._check_set_lang()
        return self.tx.ugettext

dltrans = DynLangTranslator('system-config-date')

def ugettext(message):
    return dltrans.ugettext(message)

_ = ugettext

def N_(x):
    return x
