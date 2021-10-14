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

import ConfigParser
import os
import sys
from cStringIO import StringIO
from shlex import shlex
import zipfile

if os.environ.has_key("FIRST_AID_KIT_CONF"):
    cfgfile = os.environ["FIRST_AID_KIT_CONF"].split(":")
else:
    cfgfile = ["/etc/firstaidkit/firstaidkit.conf",
            os.environ["HOME"]+"/.firstaidkit.conf"]


def createDefaultConfig(config):
    """Create the default config with the object."""
    config.operation.flags = ""
    config.operation.mode = ""
    config.operation.params = ""
    config.operation.help = "False"
    config.operation.gui = "console"
    config.operation.verbose = "False"
    config.operation.dependencies = "True"
    config.operation.interactive = "False"
    config.operation.printinfo = "False"
    config.log.method = "file"
    config.log.filename = "/var/log/firstaidkit.log"
    config.log.fallbacks = "firstaidkit.log,/tmp/firstaidkit.log,/dev/null"
    config.plugin.disabled = ""
    config.backup.method = "file"
    config.backup.rootpath = "/tmp"
    config.backup.fullpath = ""
    config.revert.all = "False"
    config.revert.dir = ""
    config.system.debug = "False"

    # Setup a sane default root directory.
    if os.path.isdir("/mnt/sysimage"):
        config.system.root = "/mnt/sysimage/"
    else:
        config.system.root = "/"

    # Set the directory containing cfg bits for different services/packages
    config.system.configuration = "/etc/firstaidkit"

    # Frontend modules are in specified directories
    config.system.frontend = ("'/usr/lib64/firstaidkit/frontend' "
            "'/usr/lib/firstaidkit/frontend' "
            "'/usr/share/firstaidkit/frontend' ")

    #
    # There will be 4 default places where FAK will look for plugins,
    # these 4 names will be reserved in the configuration.
    # lib{,64}-firstaidkit-{,examples}
    #
    config.add_section("paths")
    for dir in ["firstaidkit/plugins", "firstaidkit/plugins/examples"]:
        for root in [ "usr/lib64", "usr/lib", "usr/share"]:
            if os.path.exists( "/%s/%s" % (root,dir)):

                config.set( "paths",  "%s/%s"%(dir[19:], root[4:]),
                        "/%s/%s" %(root, dir) )


class LockedError(Exception):
    pass

class FAKConfigSection(object):
    """Proxy object for one configuration section"""

    def __init__(self, cfg, name):
        self.__dict__["__section_name"] = name
        self.__dict__["__configuration"] = cfg
        self.__dict__["__use_lock"] = True

    def lock(self):
        self.__dict__["__use_lock"] = True

    def unlock(self):
        self.__dict__["__use_lock"] = False

    def attach(self, file, saveas = None):
        self.__dict__["__configuration"].attach(file, saveas)

    def __getattr__(self, key):
        if not self.__dict__["__configuration"]. \
            has_section(self.__dict__["__section_name"]) and \
            self.__dict__["__section_name"]!="DEFAULT":

            raise ConfigParser.NoSectionError(self.__dict__["__section_name"])

        if not self.__dict__["__configuration"]. \
            has_option(self.__dict__["__section_name"], key):
            raise ConfigParser. \
                    NoOptionError(key, self.__dict__["__section_name"])

        return self.__dict__["__configuration"]. \
                get(self.__dict__["__section_name"], key)

    def __setattr__(self, key, value):
        if self.__dict__["__configuration"]. __dict__.has_key("_lock") and \
                self.__dict__["__configuration"].__dict__["_lock"] and \
                self.__dict__["__use_lock"]:
            raise LockedError(key)

        if not self.__dict__["__configuration"]. \
                has_section(self.__dict__["__section_name"]) and \
                self.__dict__["__section_name"]!="DEFAULT":
            self.__dict__["__configuration"]. \
                    add_section(self.__dict__["__section_name"])
        self.__dict__["__configuration"].set(self.__dict__["__section_name"], \
                key, value)

    def _list(self, key):
        l = []
        lex = shlex(instream = StringIO(getattr(self, key)), posix = True)
        token = lex.get_token()
        while token!=lex.eof:
            l.append(token)
            token = lex.get_token()
        return l

    def valueItems(self):
        """Usefull when you don't care about the name of the items."""
        if not self.__dict__["__configuration"]. \
                has_section(self.__dict__["__section_name"]) and \
                self.__dict__["__section_name"]!="DEFAULT":
            raise ConfigParser.NoSectionError(self.__dict__["__section_name"])
        tmpList = self.__dict__["__configuration"]. \
                items(self.__dict__["__section_name"])
        retVal = []
        for element in tmpList:
            retVal.append(element[1])
        return retVal


class FAKConfigMixIn(object):
    """Enhance ConfigParser so (config.section.value) is possible."""

    def __getattr__(self, section):
        return FAKConfigSection(self, section)

    def lock(self):
        self.__dict__["_lock"] = True

    def unlock(self):
        self.__dict__["_lock"] = False

class FAKConfig(ConfigParser.SafeConfigParser, FAKConfigMixIn):
    def getConfigBits(self, name):
        return getConfigBits(name, cfg = self)

Config = FAKConfig()
createDefaultConfig(Config)
Config.read(cfgfile)

def getConfigBits(name, cfg = Config):
    """Returns conf object loaded with bits from designated config file/service

       name - service you need info from
       cfg - configuration object containing the system.configuration value,
             to specify, where to look for the service file"""
    c = FAKConfig()
    c.read(os.path.join(cfg.system.configuration, name))
    c.lock()
    return c

class FAKInfo(ConfigParser.SafeConfigParser, FAKConfigMixIn):
    def __init__(self, *args, **kwargs):
        ConfigParser.SafeConfigParser.__init__(self, *args, **kwargs)
        FAKConfigMixIn.__init__(self)
        self._attachments = []
        self._raw_attachments = []

    def write(self, fd=sys.stdout):
        fd.write("--- Result files ---\n")
        for f,fas in self._attachments:
            fd.write("%s: %s\n" % (fas, f))
        fd.write("--- Info section ---\n")
        ConfigParser.SafeConfigParser.write(self, fd)
        fd.write("--------------------\n")

    def dump(self, filename):
        fd = zipfile.ZipFile(filename, "w", zipfile.ZIP_DEFLATED)
        temp = StringIO()
        ConfigParser.SafeConfigParser.write(self, temp)
        fd.writestr("results.ini", temp.getvalue())
        for f,fas in self._attachments:
            fd.write(f, fas)
        for c,fas in self._raw_attachments:
            fd.writestr(fas, c)
        fd.close()

    def attach(self, file, saveas = None):
        if saveas is None:
            saveas = file
        self._attachments.append((file, saveas))

    def attachRaw(self, content, saveas):
        self._raw_attachments.append((content, saveas))


class InfoProxy(object):
    __slots__ = ["_obj"]
    
    def __init__(self, obj):
        self._obj = obj

    def __getattr__(self, name):
        return getattr(self._obj, name)

Info = InfoProxy(FAKInfo())
Info.lock()

def resetInfo():
    global Info
    Info._obj = FAKInfo()
    Info.lock()
    
