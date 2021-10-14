
# File name: issue.py
# Date:      2008/03/14
# Author:    Martin Sivak <msivak at redhat dot com>
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

import uuid

class SimpleIssue(object):
    def __init__(self, name, description, remote_name = None, remote_address = None):
        self.name = name
        self.description = description
        self.remote_name = remote_name
        self.remote_address = remote_address
        self.id = uuid.uuid1()
        self.reset()

    def reset(self):
        """Reset the object's state"""
        self._checked = False
        self._happened = False
        self._fixed = False
        self._exception = None
        self._error = False
        self._skipped = False

    def set(self, happened = None, fixed = None, checked = None,
            skipped = None, error = None, 
            reporting = None, **kwreportingargs):
        """Set the state of this issue and send a report

        The report is set if reporting is not None"""
        if happened:
            self._happened = happened
        if fixed:
            self._fixed = fixed
        if checked:
            self._checked = checked
        if error:
            self._error = error
        if skipped:
            self._skipped = skipped
        if reporting:
            reporting.issue(issue = self, **kwreportingargs)

    def happened(self):
        """Get the 'issue happened' flag.

Return values:
    True - YES it happened
    False - NO, it is OK
    None - I don't know, there was an error"""
        #if the issue was fixed or not checked, the check si needed
        if not self._checked or self._error or self._skipped or self._fixed:
            return None
        else:
            return self._happened

    def fixed(self):
        """Get the 'issue fixed' flag.

Return values:
    True - YES it is fixed
    False - NO, it is still broken
    None - I don't know"""
        #if the issue was not checked, the check si needed
        if not self._checked or self._error or self._skipped:
            return None
        else:
            #issue didn't happened or is fixed -> True
            return not self._happened or self._fixed

    def skipped(self):
        return self._skipped

    def error(self):
        return self._error

    def __str__(self):
        s = []
        if self._error:
            s.append("Error evaluating")
        elif self._skipped:
            s.append("Skipped checking of")
        elif self._fixed:
            s.append("Fixed")
        elif self._happened and self._checked:
            s.append("Detected")
        elif self._checked:
            s.append("No problem with")
        else:
            s.append("Waiting for check on")

        s.append(self.name)

        if not self._error and not self._skipped and \
           self._happened and self._checked:
            s.append("--")
            s.append(self.description)

        return " ".join(s)

    def str(self):
        return self.__str__()

class Issue(SimpleIssue):
    name = "Parent issue"
    description = "This happens when you use the wrong object in the issues " \
            "list"

    def __init__(self, plugin, reporting = None):
        SimpleIssue.__init__(self, self.name, self.description)
        self._plugin = plugin
        self._reporting = reporting

    def detect(self):
        """Detect if situation happened and store some information about it.

        This is done so we can fix it
Return values:
    True - check OK
    False - check Failed
    None - no result, please continue with the operation"""

        #if the issue was fixed. the check is worthless
        #if it was checked, no need to do the check again
        if self._checked or self._fixed:
            return not self._fixed and self._checked

        #no error, please do the check (so the child-class knows to actually
        #do something)
        return None

    def fix(self):
        """Fix the situation if needed

Return values:
    True - fix OK
    False - fix Failed
    None - no result, please continue with the operation"""

        #if the issue was fixed. no need to do the fix again
        #if it was not checked, the check si needed too
        if not self._checked or self._fixed:
            return self._fixed and self._checked
        #no fix error, please do the fix (so the child-class knows to actually
        #do something)
        return None
