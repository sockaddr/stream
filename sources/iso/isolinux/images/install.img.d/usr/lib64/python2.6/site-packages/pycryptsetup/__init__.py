# File name: __init__.py
# Date:      2009/01/19
# Author:    Martin Sivak
#
# Copyright (C) Red Hat 2009
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

import cryptsetup
import fillins

class CryptSetup(cryptsetup.CryptSetup):
    """def __init__(yesDialog, logFunc)
 yesDialog - python function with func(text) signature, which asks the user question text and returns 1 of the answer was positive or 0 if not
 logFunc   - python function with func(level, text) signature to log stuff somewhere"""

    def addKey(self, device, new_passphrase=None, new_key_file=None, passphrase=None, key_file=None):
        return fillins.luks_add_key(device, new_passphrase, new_key_file, passphrase, key_file)
    
    def removeKey(self, device, del_passphrase=None, del_key_file=None, passphrase=None, key_file=None):
        return fillins.luks_remove_key(device, del_passphrase, del_key_file, passphrase, key_file)

    def prepare_passphrase_file(self, phrase):
        return fillins.prepare_passphrase_file(phrase)

