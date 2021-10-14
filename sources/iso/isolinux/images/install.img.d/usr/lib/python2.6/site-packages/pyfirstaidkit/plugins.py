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

from configuration import Config, Info
from returns import *
from errors import *
from reporting import *
from copy import copy,deepcopy
from issue import *

import FirstAidKit
import logging

import imp
import os
import re
import subprocess
from cStringIO import StringIO

Logger = logging.getLogger("firstaidkit")

class Flow(dict):
    def __init__(self, rules, description="", title="", *args, **kwargs):
        self.description = description
        self.title = title
        dict.__init__(self, rules, *args, **kwargs)

    @staticmethod
    def init(parent = None):
        if parent:
            flows = deepcopy(parent.flows)
        else:
            flows = dict()
        return flows

class Plugin(object):
    #
    # Some information vars.
    #
    name = "Plugin"
    version = "0.0.0"
    author = "nobody"
    description = ""

    #
    # Dictionary that holds all the flows.  The keys for each flow is its
    # name.  The flow will be addressed by this name.  The plugin developer
    # Can add as many flows as he wants. The developer must use the instance.
    # flows["name"] = SomeFlow.  Be aware that you can overwirhte
    # previously added flows.  This class attribute has to be initialized by
    # each plugin using flows = Flow.init(ParentClass)
    #
    flows = {}

    #
    # The initial and final states are here to give more flexibilty to the
    # Development process.  All flows will start and end with these two
    # Variables.
    #
    initial = 0
    final = 1

    #
    # This is the default flow that all classes deriving from plugin must
    # have.  As the initial state has no return value it will be indexed
    # with the parent of all Return classes.
    #
    # The flow to use with the automated repair mode
    # has to have name "fix". The flow for diagnose mode
    # has to be named "diagnose"
    #
    flows["diagnose"] = Flow({
        initial : {Return: "prepare"},
        "prepare"    : {ReturnSuccess: "diagnose", ReturnFailure: "clean",
            None: "clean"},
        "diagnose"   : {ReturnSuccess: "clean", ReturnFailure: "clean",
            None: "clean"},
        "clean"      : {ReturnSuccess: final, ReturnFailure: final, None: final}
        }, description="The default, fully automated, diagnose sequence")

    flows["fix"] = Flow({
        initial : {Return: "prepare"},
        "prepare"    : {ReturnSuccess: "diagnose", ReturnFailure: "clean",
            None: "clean"},
        "diagnose"   : {ReturnSuccess: "clean", ReturnFailure: "backup",
            None: "clean"},
        "backup"     : {ReturnSuccess: "fix", ReturnFailure: "clean",
            None: "clean"},
        "fix"        : {ReturnSuccess: "clean", ReturnFailure: "restore",
            None: "restore"},
        "restore"    : {ReturnSuccess: "clean", ReturnFailure: "clean",
            None: "clean"},
        "clean"      : {ReturnSuccess: final, ReturnFailure: final, None: final}
        }, description="The default, fully automated, fixing sequence")

    # By default, when no other parameters are passed, we use the diagnose
    # flow as the default flow to run. You can change this, BUT it MUST always
    # be a non-changing non-destructive and safe flow, which does the
    # diagnostics

    default_flow = "diagnose"

    def __init__(self, flow, reporting, dependencies, interpret = None, path = None,
            backups = None, info = None, args = None):
        """ Initialize the instance.

        flow -- Name of the flow to be used with this instance.
        reporting -- object used to report information to the user
        dependencies -- object encapsulating the inter-plugin dependency API
                        (require, provide)
        path -- directory from where was this plugin imported

        The flow is defined in the __init__ so we don't have to worry about
        changing it.
        """
        self._reporting = reporting
        self._dependencies = dependencies
        self._path = path
        self._backups = backups
        self._info = info
        self._args = args
        self._interpret = interpret

        self.provide = dependencies.provide
        self.unprovide = dependencies.unprovide
        self.require = dependencies.require

        #
        # state we are in.
        #
        self._state = Plugin.initial

        #
        # Used to hold the return value of the functions in the class.
        #
        self._result = None  #edge from the state we are in

        #
        # Choose the flow for the instance.
        #
        self.defineFlow(flow)

    def continuing(self):
        if self._interpret:
            return self._interpret.continuing()
        else:
            return True

    def call(self, step):
        """call one step from plugin"""
        self._result = None #mark new unfinished step
        self._state = step
        self._reporting.start(level = TASK, origin = self, message = step)
        r = getattr(self, step)()
        self._reporting.stop(level = TASK, origin = self, message = step)

    @classmethod
    def info(cls):
        """Returns tuple (Plugin name, Plugin version, Plugin author)"""
        return (cls.name, cls.version, cls.author)

    #
    # The flow functions.
    #
    def defineFlow(self, flow):
        """Defines the current flow to name.

        flow -- Name of the flow
        This function is to be called from the __init__ only. There will be the
        flows defined by the Plugin class and the flows defined by the actual
        plugin.  We will first search the Plugin class and then the plugin
        itself for the name.
        """
        #
        # The flow that will be used for the instance.
        #
        if flow in self.flows.keys():
            self.cflow = self.flows[flow]
        else:
            raise InvalidFlowNameException(flow)

    @classmethod
    def getFlows(cls):
        """Return a set with the names of all possible flows."""
        fatherf = cls.flows.keys()
        return set(fatherf)

    @classmethod
    def getFlow(cls, name):
        """Return a Flow object associated with provided name"""
        if cls.flows.has_key(name):
            return cls.flows[name]
        else:
            raise InvalidFlowNameException(name)

    #dependency stuff
    @classmethod
    def getDeps(cls):
        """Return list of conditions required to be set before automated rune"""
        return set()

    @classmethod
    def getConflicts(cls):
        """Return list of conditions required to be UNset before automated run"""
        return set()

    #methods available only for instance, see interpreter.py and dependency
    #stuff there
    #def require(self, id)
    #def provide(self, id)

    #list of all actions provided
    def actions(self):
        """Returns list of available actions"""
        return set(["prepare", "backup", "diagnose", "describe", "fix",
            "restore", "clean"])

    def nextstate(self, state=None, result=None):
        """Returns next state when analizing self.{_state,_result,cflow}.

        This is relevant for automode.
        state -- Name of hte function.
        result -- The return value of the previous function
        We do not check for validity of the key in the self.cflow.  If key is
        invalid, function will Traceback.  When self._state = self.final the
        function will traceback.  This situation must be handled outside this
        function.  If an automatica iteration is needed that avoids the
        necesity to address the self.final state, use __iter__ and next.
        """
        # If any of the vals are missing, we default to the current ones.
        if state is None or result is None:
            state=self._state
            result=self._result
        # The self.initial state does not have any return code.
        # It will only work with the Return.
        try:
            if state == self.initial:
                self._state = self.cflow[self.initial][Return]
            else:
                self._state = self.cflow[state][result]
            return self._state
        except KeyError:
            raise InvalidFlowStateException(self.cflow)

    #
    #iterate protocol allows us to use loops
    #
    def __iter__(self):
        self._state = self.initial
        self._result = None
        return self

    def next(self):
        """Iteration function.

        Will return (self._state, self._result).  The function that was executed
        and the return value.
        """
        func = self.nextstate()

        if func == self.final:
            raise StopIteration()
        else:
            try:
                # Execute the function.
                self.call(func)
            except Exception, e: #fallback, when there is some error in plugin
                self._reporting.exception(level = TASK, origin = self,
                        message = func+" raised "+str(e))
                self._reporting.stop(level = TASK, origin = self,
                        message = func)
                if Config.system.debug == "True":
                    raise

        return (self._state, self._result)

    #
    #default (mandatory) plugin actions
    #
    def prepare(self):
        """Initial actions.

        All the actions that must be done before the execution of any plugin
        function. This function generaly addresses things that are global to
        the plugin.
        """
        #We want these functions to be overridden by the plugin developer.
        if self.__class__ is Plugin:
            Logger.warning("Prepare is an abstract method, it should be used "
                    "as such.")

    def clean(self):
        """Final actions.

        All the actions that must be done after the exection of all plugin
        functions. This function generaly addresses things that are global
        and need to be closed off, like file descriptos, or mounted
        partitions....
        """
        #We want these functions to be overridden by the plugin developer.
        if self.__class__ is Plugin:
            Logger.warning("Clean is an abstract method, it should be used as "
                    "such.")

    def backup(self):
        """Gather important information needed for restore."""
        #We want these functions to be overridden by the plugin developer.
        if self.__class__ is Plugin:
            Logger.warning("Backup is an abstract method, it should be used as "
                    "such.")

    def restore(self):
        """Try to restore the previous state described in backup."""
        #We want these functions to be overridden by the plugin developer.
        if self.__class__ is Plugin:
            Logger.warning("Restore is an abstract method, it should be used "
                    "as such.")

    def diagnose(self):
        """Diagnose the situation."""
        #We want these functions to be overridden by the plugin developer.
        if self.__class__ is Plugin:
            Logger.warning("Diagnose is an abstract method, it should be used "
                    "as such.")

    def fix(self):
        """Try to fix whatever is wrong in the system."""
         #We want these functions to be overridden by the plugin developer.
        if self.__class__ is Plugin:
            Logger.warning("Fix is an abstract method, it should be used as "
                    "such.")

class IssuesPlugin(Plugin):
    """Plugin which uses Issue classes to test smaller and INDEPENDENT issues.

    Just fill the issue_tests list with classes describing the tests and let
    it run."""

    issue_tests = [] #List of Issue classes to check
    set_flags = [] #flags to set when everything is OK

    def __init__(self, *args, **kwargs):
        Plugin.__init__(self, *args, **kwargs)
        self.tests = []

    def prepare(self):
        """Prepare the issues list"""
        for i in self.issue_tests:
            self._reporting.info(level = TASK, origin = self,
                    message = "Preparing tests for '%s'" % (i.name,))
            issue = i(plugin = self)
            self.tests.append(issue)
            self._reporting.issue(level = TASK, origin = self, issue = issue)
        self._result=ReturnSuccess

    def diagnose(self):
        """Diagnose the situation."""

        result = False
        happened = False
        for i in self.tests:
            self._reporting.info(level = TASK, origin = self,
                    message = "Investigating '%s'" % (i.name,))
            result = result or i.detect()
            self._reporting.issue(level = TASK, origin = self, issue = i)
            if i.happened():
                happened = True
                self._reporting.info(level = TASK, origin = self,
                        message = i.str())

        if result and not happened:
            self._result=ReturnSuccess
            for flag in self.set_flags:
                self._dependencies.provide(flag)
        elif result:
            self._result=ReturnFailure
        else:
            self._result = None

    def fix(self):
        """Try to fix whatever is wrong in the system."""

        result = False
        fixed = True
        for i in self.tests:
            self._reporting.info(level = TASK, origin = self,
                    message = "Fixing '%s'" % (i.name,))
            result = result or i.fix()
            self._reporting.issue(level = TASK, origin = self, issue = i)
            if not i.fixed():
                fixed = False
                continue

            i.reset()
            if not i.detect() or i.happened():
                self._reporting.issue(level = TASK, origin = self, issue = i)
                fixed = False

        if result and fixed:
            self._result=ReturnSuccess
            for flag in self.set_flags:
                self._dependencies.provide(flag)
        elif result:
            self._result=ReturnFailure
        else:
            self._result = None


class FlagTrackerPlugin(Plugin):
    """This kind of plugin monitores all the flags in the system and when
    certain flags are set, provides some kind of higher level flag.

    Example:
      monitor flags 'filesystem_drive', 'filesystem_lvm' and 'filesystem_ext3'
      and if everything is ok set the master flag 'filesystem'"""

    # Higher level master flag to set
    #flag_decide = "x_decide"
    flag_decide = None

    # List of flags which have to be set for the higher level flag to be set
    #flag_list = ["x_decide_1", "x_decide_2"]
    flag_list = []

    # Wait before we have acquired results from all needed flags
    @classmethod
    def getDeps(cls):
        return set([x+"?" for x in cls.flag_list])

    #
    # This is the default flow that all classes deriving from plugin must
    # have.  As the initial state has no return value it will be indexed
    # with the parent of all Return classes.
    #
    # The flow to use with the automated repair mode
    # has to have name "fix". The flow for diagnose mode
    # has to be named "diagnose"
    #

    flows = Flow.init(Plugin)
    flows["diagnose"] = Flow({
            Plugin.initial : {Return: "decide"},
            "decide"    : {Return: Plugin.final}
            }, description="The default, fully automated, deciding sequence")
    flows["fix"] = flows["diagnose"]

    def decide(self):
        """Decide about state of higher level flags."""
         #We want these functions to be overridden by the plugin developer.
        if self.__class__ is FlagTrackerPlugin:
            Logger.warning("Decide is an abstract method, it should be used "
                    "as such.")

        if self.flag_decide is None:
            Logger.warning("You have to specify flag to set when everything "
                    "is ok.")
            return Return

        for flag in self.flag_list:
            if not self._dependencies.require(flag):
                return Return

        self._dependencies.provide(self.flag_decide)
        return Return


class PluginSystem(object):
    """Encapsulate all plugin detection and import stuff"""

    name = "Plugin System"

    def __init__(self, interpret, reporting, dependencies, config=Config, backups=None):
        self._paths = Config.paths.valueItems()
        self._backups = backups
        self._reporting = reporting
        self._reporting.start(level = PLUGINSYSTEM, origin = self)
        self._deps = dependencies
        self._interpret = interpret
        self._plugins = {}
        self._flow_titles = {}

        for path in self._paths:
            if not os.path.isdir(path):
                self._reporting.debug("The path %s does not exist" % path,
                        level = PLUGINSYSTEM, origin = self)
                continue
            #create list of potential modules in the path
            importlist = set()
            for f in os.listdir(path):
                fullpath = os.path.join(path, f)
                self._reporting.debug("Processing file: %s" % (f,),
                        level = PLUGINSYSTEM, origin = self)
                if os.path.isdir(fullpath) \
                    and os.path.isfile(os.path.join(path, f, "__init__.py")):
                    importlist.add(f)
                    self._reporting.debug("Adding python module (directory): %s"
                            % (f,), level = PLUGINSYSTEM, origin = self)

                elif os.path.isfile(fullpath) and (f[-3:]==".so"
                        or f[-3:]==".py"):
                    importlist.add(f[:-3])
                    self._reporting.debug("Adding python module (file): %s"
                            % (f,), level = PLUGINSYSTEM, origin = self)

                elif os.path.isfile(fullpath) and (f[-4:]==".pyc"
                        or f[-4:]==".pyo"):
                    importlist.add(f[:-4])
                    self._reporting.debug("Adding python module (compiled): %s"
                            % (f,), level = PLUGINSYSTEM, origin = self)

            #try to import the modules as FirstAidKit.plugins.modulename
            for m in importlist:
                if m in Config.plugin._list("disabled"):
                    continue

                imp.acquire_lock()
                try:
                    self._reporting.debug("Importing module %s from %s"
                            % (m, path), level = PLUGINSYSTEM, origin = self)
                    moduleinfo = imp.find_module(m, [path])
                    module = imp.load_module(".".join([FirstAidKit.__name__,m]),
                            *moduleinfo)
                    #notify the dependency system about all used dependencies
                    self._deps.introduce(module.get_plugin().getDeps())
                    #notify the dependency system about all used
                    #reverse-dependencies
                    self._deps.introduce(module.get_plugin().getConflicts())
                    self._plugins[m] = module
                    self._reporting.debug("Module %s successfully imported "
                            "with basedir %s" %
                            (m, os.path.dirname(module.__file__)),
                            level = PLUGINSYSTEM, origin = self)
                except Exception, e:
                    self._reporting.error(message = "Module %s was NOT "
                            "imported, because of %s" %
                            (m, str(e)), level = PLUGINSYSTEM, origin = self)
                finally:
                    imp.release_lock()
            
        #initialize gettext
        trans = None
        try:
            import gettext
            trans = gettext.translation('firstaidkit')
        except Exception as e:
            pass
            
        #get flow titles from plugins
        for m in self._plugins:
            plugin = self.getplugin(m)
            for flowname in plugin.getFlows():
                flow = plugin.getFlow(flowname)
                
                #we already have title
                if flowname in self._flow_titles and self._flow_titles[flowname]:
                    continue
                
                #get best title
                gt = trans.lgettext(flowname) if trans else flowname
                title = gt if gt != flowname else flow.title

                self._flow_titles[flowname] = title
        
        #set title for flow with no title
        for flow, title in self._flow_titles.iteritems():
            if not title:
                self._flow_titles[flow] = flow

    def list(self):
        """Return the list of imported plugins"""
        return self._plugins.keys()
        
    def get_title(self, flow):
        """Return flow title"""
        return self._flow_titles[flow]

    def autorun(self, plugin, flow = None, dependencies = True):
        """Perform automated run of plugin with condition checking

        returns - True if conditions are fully satisfied
        False if there is something missing
        exception when some other error happens"""

        self._reporting.start(level = PLUGIN, origin = self, message = plugin)

        if plugin in self._plugins.keys():
            #get top level class of plugin
            pklass = self._plugins[plugin].get_plugin()
        else:
            self._reporting.exception(message = "Plugin %s was not found" %
                    plugin, level = PLUGINSYSTEM, origin = self)
            self._reporting.stop(level=PLUGIN, origin=self, message=plugin)
            raise InvalidPluginNameException(plugin)

        plugindir = os.path.dirname(self._plugins[plugin].__file__)
        self._reporting.info(message = "Plugin information...", \
                level = PLUGINSYSTEM, origin = self)
        self._reporting.info(message = "name:%s , version:%s , author:%s " \
                % pklass.info(), level = PLUGINSYSTEM, origin = self)

        flows = pklass.getFlows()
        self._reporting.info(message = "Provided flows : %s " % flows, \
                level = PLUGINSYSTEM, origin = self)
        if flow==None:
            flowName = pklass.default_flow
        else:
            flowName = flow

        self._reporting.info(message = "Using %s flow" % flowName, \
                level = PLUGINSYSTEM, origin = self)
        if flowName not in flows:
            self._reporting.exception(message = "Flow %s does not exist in "
                    "plugin %s" % (flowName, plugin), level = PLUGINSYSTEM,
                    origin = self)
            self._reporting.stop(level=PLUGIN, origin=self, message=plugin)
            raise InvalidFlowNameException(flowName)

        if dependencies:
            deps = pklass.getDeps()
            if len(deps)>0:
                self._reporting.info(message = "depends on: %s" % \
                        (", ".join(deps),), level = PLUGINSYSTEM, \
                        origin = self)
                for d in deps:
                    if not self._deps.require(d):
                        self._reporting.info(message = "depends on " \
                                "unsatisfied condition: %s" % (d,), \
                                level = PLUGINSYSTEM, origin = self)
                        self._reporting.stop(level = PLUGIN, origin = self,
                                message = plugin)
                        return False
            deps = pklass.getConflicts()
            if len(deps)>0:
                self._reporting.info(message = "depends on flags to be unset: %s" % \
                        (", ".join(deps),), level = PLUGINSYSTEM, origin = self)
                for d in deps:
                    if self._deps.require(d):
                        self._reporting.info(message = "depends on condition to be " \
                                "UNset: %s" % (d,), level = PLUGINSYSTEM, \
                                origin = self)
                        self._reporting.stop(level = PLUGIN, origin = self,
                                message = plugin)
                        return False

        args = []
        if Config.has_section("plugin-args"):
            for (name, value) in Config.items("plugin-args"):
                # We see if the args line begins with any plugin name.
                m = re.search("^%s "%plugin, value)
                if m:
                    args.append(value.lstrip(plugin).strip(" "))
                # We also want to be able to configure separate flows
                m = re.search("^%s/%s "% (plugin, flowName), value)
                if m:
                    args.append(value.lstrip(plugin+'/'+flowName).strip(" "))

        infosection = getattr(Info, plugin)
        infosection.unlock()
        p = pklass(flowName, interpret = self._interpret, reporting = self._reporting,
                dependencies = self._deps, backups = self._backups,
                path = plugindir, info = infosection, args = " ".join(args))
        for (step, rv) in p: #autorun all the needed steps
            self._reporting.info(message = "Running step %s in plugin %s ..."% \
                    (step, plugin), level = PLUGINSYSTEM, origin = self)
            self._reporting.info(message = "%s is current step and %s is result " \
                    "of that step." % (step, rv), level = PLUGINSYSTEM, \
                    origin = self)

        self._reporting.stop(level = PLUGIN, origin = self, message = plugin)
        return True

    def getplugin(self, plugin):
        """Get top level class of plugin, so we can create the instance and
        call the steps manually"""
        if plugin in self._plugins:
            return self._plugins[plugin].get_plugin()
        else:
            raise InvalidPluginNameException(plugin)
