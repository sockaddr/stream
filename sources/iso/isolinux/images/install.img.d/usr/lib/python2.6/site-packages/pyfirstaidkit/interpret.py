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

import os
import sys
from plugins import PluginSystem
from reporting import Reports, TASKER, PLUGINSYSTEM, FIRSTAIDKIT, END, ISSUE
import logging
import copy
from errors import *
from utils import FileBackupStore
from dependency import Dependencies
from configuration import Info, getConfigBits
from threading import Thread
from issue import SimpleIssue
import subprocess
import cPickle as pickle
import ConfigParser

class RemoteTask(Thread):
    def __init__(self, reporting, name, address, configData):
        Thread.__init__(self)
        self.state = SimpleIssue("Remote run on %s" % name, address)
        self.conn = None
        self.cfg = getConfigBits(configData)
        self.reporting = reporting
        self.name = name
        self.address = address
        
    def run(self):
        running = True
        self.reporting.issue(issue = self.state, level = FIRSTAIDKIT, origin = self)
        self.conn = subprocess.Popen(["ssh", "-q", "-T", self.address, "firstaidkit-shell"],
                                stdin = subprocess.PIPE, stdout = subprocess.PIPE, stderr = subprocess.PIPE,
                                bufsize = 1, close_fds = True)

        welcomeLine = self.conn.stdout.readline()
        # start wasn't successful
        if not welcomeLine.startswith("[firstaidkit-shell] Ready"):
            self.state.set(checked = True, happened = True, reporting = self.reporting, origin = self)
            if welcomeLine.startswith("The autenticity "): # ssh waiting for the fingerprint
                (report_file, stderr) = self.conn.communicate("no\n")
            else:
                (report_file, stderr) = self.conn.communicate()
            return
        
        self.cfg.write(self.conn.stdin)
        self.conn.stdin.write("\n[commit]\n")

        welcomeLine = self.conn.stdout.readline()
        # config wasn't successful
        if not welcomeLine.startswith("[firstaidkit-shell] Starting"):
            self.state.set(checked = True, happened = True, reporting = self.reporting, origin = self)
            (report_file, stderr) = self.conn.communicate("[abort]\n")
            return
        else:
            self.state.set(checked = True, happened = False, reporting = self.reporting, origin = self)
            
        while running:
            try:
                msg = pickle.load(self.conn.stdout)
            except pickle.UnpicklingError, e:
                print e
                raise
            if msg["level"]==FIRSTAIDKIT and msg["action"]==END:
                running = False

            # set issue origin if it comes from this machine
            if not msg["remote"] and msg["action"] == ISSUE:
                msg["message"].remote_name = self.name
                msg["message"].remote_address = self.address

            # set message origin and remote state so nobody changes the origin again
            if not msg["remote"]:
                msg["remote"] = True
                msg["remote_name"] = self.name
                msg["remote_address"] = self.address
                
            self.reporting.put_raw(msg)
            
        report_file = self.conn.stdout.read()
        stderr = self.conn.stderr.read()
        Info.attachRaw(report_file, "remote_report_%s.zip" % self.name)
        self.conn.wait()

class Tasker(object):
    """The main interpret of tasks described in Config object"""

    name = "Task interpreter"

    def __init__(self, cfg, reporting = None, dependencies = None,
            backups = None, pluginsystem = None):
        self._config = cfg
        self._running = True

        if dependencies is None:
            self._provide = Dependencies()
        else:
            self._provide = dependencies

        if reporting is None:
            self._reporting = Reports()
        else:
            self._reporting = reporting

        if backups is None:
            if cfg.backup.fullpath:
                # rootpath is silly if fullpath is set by user.
                cfg.backup.rootpath = ""

            self._backups = FileBackupStore(rootpath = cfg.backup.rootpath,
                    fullpath = cfg.backup.fullpath)
            cfg.backup.fullpath = self._backups._path
        else:
            self._backups = backups

        if pluginsystem is None:
            self.pluginSystem = PluginSystem(interpret = self, reporting = self._reporting,
                    dependencies = self._provide, backups = self._backups)
        else:
            self.pluginSystem = pluginsystem

    def interrupt(self):
        self._running = False
        self._reporting.info("You sent an interrupt signal to "
                "Tasker! This is not recommended.", level = TASKER,
                origin = self, importance = logging.WARNING)

    def continuing(self):
        return self._running

    def flags(self):
        return self._provide

    def reporting(self):
        return self._reporting

    def pluginsystem(self):
        return self.pluginSystem

    def end(self):
        """Signalize end of operations to all necessary places"""
        self._reporting.end(origin = self, level = FIRSTAIDKIT)

    def run(self):
        self._reporting.start(level = TASKER, origin = self)
        pluginSystem = self.pluginSystem

        # Reset the flag state
        self._provide.reset()

        # Check the root privilegies
        if os.geteuid() == 0:
            self._reporting.info("You are running the firstaidkit as root.",
                    level = TASKER, origin = self, importance = logging.WARNING)
            self._provide.provide("root")
        else:
            self._reporting.info("You are not running the firstaidkit as "
                    "root.  Some plugins may not be available.", level = TASKER,
                    origin = self, importance = logging.WARNING)
            self._provide.unprovide("root")

        # Initialize the interactivity
        if self._config.operation.interactive == "True":
            self._provide.provide("interactive")

        # Initialize the startup set of flags
        for flag in self._config.operation._list("flags"):
            self._provide.provide(flag)

        # For the auto, auto-flow, plugin, flow cases.
        if self._config.operation.mode in ("auto", "auto-flow", "plugin",
                "flow", "monitor"):

            if self._config.operation.mode == "plugin":
                pluginlist = self._config.operation._list("plugin")
            elif self._config.operation.mode == "monitor":
                pluginlist = []
            else:
                pluginlist = set(pluginSystem.list())

            if self._config.operation.mode == "auto-flow":
                flows = len(pluginlist)*[self._config.operation.flow]
            elif self._config.operation.mode == "flow":
                flows = self._config.operation._list("flow")
                pluginlist = self._config.operation._list("plugin")
            else:
                flows = len(pluginlist)*[None]

            #prepare remote tasks
            remoteThreads = []
            if self._config.has_section("remote"):
                targets = self._config.items("remote")
                for (name, spec) in targets:
                    address, cfg = spec.split(None, 1)
                    remoteThreads.append(RemoteTask(self._reporting, name, address, cfg))

            #start remote tasks
            for th in remoteThreads:
                th.start()

            #iterate through plugins until there is no plugin left or no
            #action performed during whole iteration
            oldlist = set()
            actlist = set(zip(pluginlist, flows))

            self._running = True
            while self._running and len(actlist)>0 and oldlist!=actlist:
                oldlist = copy.copy(actlist)

                for plugin,flow in oldlist:
                    #If interruption was requested, stop
                    if not self._running:
                        break
                    
                    #If plugin does not contain the automated flow or if
                    #it ran correctly, remove it from list
                    if ((flow and
                        not flow in pluginSystem.getplugin(plugin).getFlows())
                        or (not flow and
                            not pluginSystem.getplugin(plugin).default_flow in
                            pluginSystem.getplugin(plugin).getFlows())):

                        self._reporting.info("Plugin %s does not contain "
                                "flow %s"% (plugin, flow or \
                                pluginSystem.getplugin(plugin).default_flow,), \
                                level = TASKER, origin = self)

                        actlist.remove((plugin, flow))

                    elif (pluginSystem.autorun(plugin, flow = flow,
                            dependencies = self._config.operation.dependencies
                            != "False")):
                        actlist.remove((plugin, flow))

            #some plugins may not be called because of unfavorable flags
            if self._running:
                for plugin in set(map(lambda x: x[0], actlist)):
                    self._reporting.info("Plugin %s was not called because of "
                                         "unsatisfied dependencies"% (plugin,), level = TASKER, \
                                         origin = self, importance = logging.WARNING)

            #wait until the remotes finish
            for th in remoteThreads:
                th.join()
                
        # For the flags case
        elif self._config.operation.mode == "flags":
            self._reporting.table(self._provide.known(), level = TASKER,
                    origin = self, title = "List of flags")

        # For the list case
        elif self._config.operation.mode == "list":
            #get list of plugins
            rep = []
            for k in pluginSystem.list():
                p = pluginSystem.getplugin(k)
                flowinfo = [(f, p.getFlow(f).description) for f in p.getFlows()]
                rep.append((k, p.name, p.version, p.author, p.description,
                    p.default_flow, flowinfo))
            self._reporting.table(rep, level = TASKER, origin = self,
                    title = "List of plugins")

        # For the info case
        elif self._config.operation.mode == "info":
            #get info about plugin
            try:
                p = pluginSystem.getplugin(self._config.operation.params)
            except KeyError:
                self._reporting.info(message = "No such plugin '%s'" % \
                        (self._config.operation.params,), level = TASKER, \
                        origin = self)
                return False
            flowinfo = [ (f, p.getFlow(f).description) for f in p.getFlows() ]
            rep = {"id": self._config.operation.params, "name": p.name,
                    "version": p.version, "author": p.author,
                    "description": p.description, "flow": p.default_flow,
                    "flows": flowinfo}
            self._reporting.tree(rep, level = TASKER, origin = self,
                    title = "Information about plugin %s" % \
                            (self._config.operation.params,))

        # Any other case
        else:
            self._reporting.info(message = "Incorrect task specified", \
                    level = TASKER, origin = self)
            self._reporting.stop(level = TASKER, origin = self)
            return False

        if self._config.operation.printinfo == "True":
            Info.write()

        self._reporting.stop(level = TASKER, origin = self)
        return True
