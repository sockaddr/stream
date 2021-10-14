#!/usr/bin/python
# 
# Copyright 2005-2007 Red Hat, Inc.
# 
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) version 3.
# 
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
# 
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
# 

import dm

from maps import *
from device import MultiPath, RaidDev, RaidSet, BlockDev, DeviceMaps, \
                   removeDeviceMap

_log_ignore = False
_verbose = dm.log_warn

def dm_log(level, file, line, message):
    if _log_ignore:
        return;
    if level == dm.log_fatal or level == dm.log_err:
        raise Exception, message
        #print "%s" % (message,)
        pass
    elif level == dm.log_warn:
        raise RuntimeWarning, message
        #print "%s" % (message,)
        pass
    elif level <= _verbose:
        print "%s" % (message,)
        pass

dm.set_logger(dm_log)
del dm_log

import dmraid

def getDevice(name):
    """Retrieve a major and minor number for a specific path/name.

    The last word after the '/' in name is used to search for the device.
    """
    name = name.split('/')[-1]
    maps = dm.maps()
    for map in maps:
        if name == map.name:
            return (map.dev.major, map.dev.minor)

def getRaidSets(*disks):
    """Retrieve all the raid sets in the system.

    Returns a list of RaidSet objects.
    """
    # make it so you don't have to apply() to pass a list
    old = disks
    disks = []
    for disk in old:
        if isinstance(disk, [].__class__) or isinstance(disk,().__class__):
            disks += list(disk)
        else:
            disks.append(disk)

    c = dmraid.context()
    rsList = []
    prefix = "/dev/mapper/"

    newdisks = []
    import os as _os
    for x in range(len(disks)):
        if not disks[x].startswith('/'):
            devdisk = '/dev/' + disks[x]
            tmpdisk = '/tmp/' + disks[x]

            if _os.access(devdisk, _os.F_OK):
                disks[x] = devdisk
            elif _os.access(tmpdisk, _os.F_OK):
                disks[x] = tmpdisk
    del _os
    disks = disks + newdisks

    try:
        for rs in c.get_raidsets(disks):
            set = RaidSet(rs, prefix=prefix)
            if set.valid:
                rsList.append(set)
    except dmraid.GroupingError:
        # Sometimes libdmraid fails to build a list of raidsets with a
        # "group_set failed" error, treat this as if no sets were found.
        pass

    return rsList

def getRaidSet(name, prefix="/dev/mapper"):
    """Get a raid set by name."""
    c = dmraid.context()
    for rs in c.get_raidsets([]):
        if rs.name == name:
            set = RaidSet(rs, prefix=prefix)
            # FIXME: should raise some type of error if this is false.
            # FIXME: should we do something different when degraded?
            if set.valid:
                return set
    return None

def getMap(uuid = None, major = None, minor = None, name = None):
    """ Return a map that matches the given parameters.

    uuid and name are strings.  major and minor are converted to long before
    being compared.

    major and minor should be specified as a pair -- that is to say one
    should either give both of them or neither of them.

    Returns None if the map is not found.
    """
    # don't bother if there are no specs to search for
    if uuid is None and major is None and minor is None and name is None:
        return None

    # Return None if we don't find the map.
    map = None
    for _map in dm.maps():
        if (name is None or \
            (_map.name is not None and _map.name == name)) and\
           (uuid is None or \
            (_map.uuid is not None and _map.uuid == uuid)) and\
           ((major is None or minor is None) or \
            (_map.dev.major is not None and _map.dev.minor is not None and \
             _map.dev.major == long(major) and _map.dev.minor == long(minor))):
            map = _map
            break

    return map

def getDmDeps(uuid = None, major = None, minor = None, name = None):
    """ Retrieve the deps for a specified map/device.

    uuid and name are strings.  major and minor are converted to long before
    being compared.

    Returns a set of deps for the device.
    Returns () when no deps are found for the specified device.
    Returns None when device was not found.
    """
    map = getMap(uuid=uuid, major=major, minor=minor, name=name)
    try:
        deps = map.deps
    except AttributeError:
        deps = ()
    return deps

def getDmTarget(uuid = None, major = None, minor = None, name = None):
    """ Retrieve the target for a specified map/device.

    uuid and name are strings.  major and minor are converted to long before
    being compared.

    Returns a string.
    Returns None when device was not found.

    Note: None is returned if map.table.type is None.
    """
    map = getMap(uuid=uuid, major=major, minor=minor, name=name)
    try:
        target = map.table[0].type
    except AttributeError:
        target = None
    return target

def getNameFromDmNode(dm_node):
    """ Return the related name for the specified node.

    Expects a device node with or without the "/dev" prefix.

    Returns a String representing the name.  None if the major, minor
    pair was not found in the maps list.
    """

    if not dm_node.startswith("/dev"):
        import os.path as _path
        dm_node = _path.join("/dev", dm_node)
        del _path

    import os as _os
    stat = _os.stat(dm_node)
    major = long(_os.major(stat.st_rdev))
    minor = long(_os.minor(stat.st_rdev))
    del _os

    for map in dm.maps():
        if map.dev.major == major and map.dev.minor == minor:
            return map.name

    # In case the major, minor pair is not found in maps.
    return None


def getDmNodeFromName(name):
    """ Return the related node for the specified name.

    Expects a string representing the name.

    Returns dm-MINOR if the map list contains the specified name.
    None if name was not found.
    """
    for map in dm.maps():
        if map.name == name:
            return "dm-%s" % map.dev.minor

    return None

def getMemFromRaidSet(rs, uuid=None, major=None, minor=None, name=None):
    """ Retrieve the object of specified member of RaidSet rs.

    uuid and name are strings.  major and minor are converted to long before
    being compared.  name is the dev name without the path.

    Returns an Ojbect.
    Returns None on failure.
    """
    if not isinstance(rs, RaidSet):
        return None

    kwargs = {"uuid":uuid, "name":name, "major":major, "minor":minor}
    for mem in rs.members:
        # We can actually come across two types of objects: RaidDev and RaidSet
        if isinstance(mem, RaidSet):
            if (mem.name is not None and mem.name == name) or \
                    (mem.bdev != None and # Intermediate rs's dont have bdev
                     mem.bdev.major != None and mem.bdev.major == major and \
                     mem.bdev.minor != None and mem.bdev.minor == minor):
                return mem
            ret = getMemFromRaidSet(mem, **kwargs)
            if ret != None:
                return ret

        elif isinstance(mem, RaidDev):
             if (mem.devpath is not None and mem.devpath == name) or \
                    (mem.bdev.major != None and mem.bdev.major == major and \
                     mem.bdev.minor != None and mem.bdev.minor == minor):
                return mem
        else:
            # We will fail if we recieve something we don't expect
            return None

    return None

def getRaidSetFromRelatedMem(uuid=None, major=None, minor=None, name=None):
    """ Retrieve the set name of the related device.

    uuid and name are strings.  major and minor are converted to long before
    being compared.  name is the dev name without the path.

    Returns a list of sets.
    Returns an empty list if no set is related to the specified device.
    """
    retval = []
    kwargs = {"uuid":uuid, "name":name, "major":major, "minor":minor}
    for rs in getRaidSets():
        if  getMemFromRaidSet(rs, **kwargs) != None:
            retval.append(rs)

    return retval

__all__ = [ "dm", "dmraid", "BlockDev" ]

#
# vim:ts=8:sts=4:sw=8:et
#
