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


#
# These classes expressed here are to be the keys in the flow dictionary.
# In most default cases the attributes are unimportant.  They are placed there
# for printing or other purposes.
# Think of those classes as of predefined constants.
#

class Return:
    """Its just a parent class for any Return class that might be create."""
    def __init__(self):
        pass

class ReturnTrue(Return):
    pass

class ReturnFalse(Return):
    pass

class ReturnNone(Return):
    pass

class ReturnBack(Return):
    pass

class ReturnAbort(Return):
    pass

#
# The Success and Failure return classes are implemented to give a more
# intuitive/logical approach to the default flow.  The value given to the return
# of each task depends on the objectives of the task and of the place where the
# task is situated inside the totality of the flow.
# Examples:
# 1. If the plugin is in the diagnose flow and if found nothing wrong with the
#    system it is analysing, the return value would be Success.
# 2. If the plugin is in backup and the backup action is unseccessfull, the
#    proper return value would be Failure.  In this Success would mean that
#    the backup was successfull and the plugin can move toward the fix task.
# 3. If the plugin is in fix stage and the problem was not fixed, the return
#    value should be Failure.  On the other hand if the fix has been done
#    the return value should be Success.
# Remember that the actual values of the classes is not checked,  what is
# checked
# is that the return value be the specific class.
#

class ReturnSuccess(Return):
    """Use whenever the result of a task is positive, expected or offers the
    least resistence.
    """
    pass

class ReturnFailure(Return):
    """Used whenever the result of a task is not possitive, not expected or
    offers the most resistence.
    """
    pass

